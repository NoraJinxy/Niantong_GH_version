"""
Purpose: 极简 ELYS REST client —— 所有 projects/* 共用。
Related: 跟 deploy 无关，独立调试用。靠 ELYS 应用账号密码（不是 SSH）。

各 project 里这样用：
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).parents[2] / "common"))
    from elys_client import ElysClient
"""
from __future__ import annotations

import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Iterator

import requests


class ElysAPIError(RuntimeError):
    """API 返回非 2xx。带上状态码 / 方法 / URL / 响应体，直接看到后端真正的报错原因
    （标准的 raise_for_status() 只给状态码，不给响应体，排错很费劲）。"""

    def __init__(self, response: requests.Response):
        self.response = response
        self.status_code = response.status_code
        body = (response.text or "").strip()
        if len(body) > 2000:
            body = body[:2000] + " …(已截断)"
        method = response.request.method if response.request is not None else "?"
        super().__init__(
            f"HTTP {response.status_code} {response.reason}  [{method} {response.url}]\n"
            f"  响应体: {body or '(空)'}"
        )


def _raise_for_status(response: requests.Response) -> requests.Response:
    """类似 r.raise_for_status()，但 4xx/5xx 时把响应体一并抛出。"""
    if not response.ok:
        raise ElysAPIError(response)
    return response


def _format_speed(bytes_per_sec: float) -> str:
    """把「字节/秒」格式化成自适应单位的人类可读速度，如 '2.3 MB/s'。速度无效时返回 '--'。"""
    if not bytes_per_sec or bytes_per_sec <= 0:
        return "--"
    value = float(bytes_per_sec)
    for unit in ("B/s", "KB/s", "MB/s", "GB/s"):
        if value < 1024 or unit == "GB/s":
            digits = 0 if unit == "B/s" or value >= 100 else 1
            return f"{value:.{digits}f} {unit}"
        value /= 1024
    return f"{value:.1f} GB/s"


class _StreamingBody:
    """带 __len__ 的可迭代请求体。

    为什么需要它：requests 拿到一个**裸生成器**当 body 时，因为算不出长度，会自动加
    `Transfer-Encoding: chunked`；要是再手动塞了 `Content-Length`，俩头同时出现属畸形请求，
    有些代理 / 网关会直接重置连接（实测本机 clash 代理就这么挂的）。给 body 一个 __len__，
    requests 就改用 Content-Length 直传、不发 chunked——和旧的 files= 缓冲上传同样规矩，
    但仍是边读盘边发，进度条照常。
    """

    def __init__(self, chunks: "Iterator[bytes]", length: int):
        self._chunks = chunks
        self._length = length
        self._buf = b""
        self._done = False

    def __len__(self) -> int:
        return self._length

    def __iter__(self):
        # requests 靠 __iter__ 把它判定为「流式 body」从而设 Content-Length；
        # 实际传输走下面的 read()（http.client/urllib3 优先用 read，更通用）。
        return self._chunks

    def read(self, amt: int | None = -1) -> bytes:
        if amt is None or amt < 0:                 # 读全部剩余
            rest = b"".join(self._chunks)
            out, self._buf, self._done = self._buf + rest, b"", True
            return out
        while len(self._buf) < amt and not self._done:
            try:
                self._buf += next(self._chunks)
            except StopIteration:
                self._done = True
        out, self._buf = self._buf[:amt], self._buf[amt:]
        return out


def _encode_multipart_stream(
    text_fields: dict[str, str],
    file_specs: list[tuple[str, Path]],
    *,
    chunk_size: int = 256 * 1024,
    on_progress: Callable[[int, int], None] | None = None,
) -> tuple[_StreamingBody, str, int]:
    """手写 multipart/form-data 的「流式」编码：边读盘边发，发的同时回报进度。

    为什么不用 requests 自带的 files=：它会把整个请求体先攒进内存算 Content-Length 再发，
    给不了「发了多少字节」的钩子，画不出上传进度条。这里自己拼分隔线、自己数字节。

    text_fields: 普通表单字段（subject/task/...），值会被 str() 后当文本发。
    file_specs:  [(字段名, 文件路径)]，每个文件作为一个 form-data part。
    返回 (body 生成器, Content-Type 头, Content-Length)。后两者要原样塞进请求头。
    """
    boundary = uuid.uuid4().hex
    crlf = b"\r\n"
    # parts: (kind, header_bytes, payload, part_size)  payload 对文本是 bytes、对文件是 Path
    parts: list[tuple[str, bytes, Any, int]] = []
    for name, value in text_fields.items():
        header = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
        ).encode()
        body = str(value).encode()
        parts.append(("data", header, body, len(header) + len(body) + len(crlf)))
    for name, path in file_specs:
        header = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"; filename="{path.name}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode()
        size = path.stat().st_size
        parts.append(("file", header, path, len(header) + size + len(crlf)))
    closing = f"--{boundary}--\r\n".encode()
    total = sum(p[3] for p in parts) + len(closing)

    def _body() -> Iterator[bytes]:
        sent = 0

        def emit(chunk: bytes) -> bytes:
            nonlocal sent
            sent += len(chunk)
            if on_progress is not None:
                on_progress(sent, total)
            return chunk

        for kind, header, payload, _ in parts:
            yield emit(header)
            if kind == "data":
                yield emit(payload)
            else:
                with open(payload, "rb") as fh:
                    while True:
                        chunk = fh.read(chunk_size)
                        if not chunk:
                            break
                        yield emit(chunk)
            yield emit(crlf)
        yield emit(closing)

    content_type = f"multipart/form-data; boundary={boundary}"
    return _StreamingBody(_body(), total), content_type, total


class ElysClient:
    def __init__(self, base_url: str, username: str, password: str, timeout: int = 60, data_base_url: str | None = None):
        self.base_url = base_url.rstrip("/")
        # 大数据端点（文件上传 / 下载）直连计算服 data_base_url；不传则跟随 base_url（行为不变）。
        # 入口服出网带宽低、16MB 经它中转固定 ~38s，故文件不走入口服；轻 API（登录/建库/轮询）仍走 base_url。
        self.data_base_url = (data_base_url or base_url).rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self._session = requests.Session()
        # 直连，不吃任何代理：requests 默认 trust_env=True 会读系统代理 / HTTP(S)_PROXY 环境变量，
        # 于是上传被 Clash 等本地代理（曾见 127.0.0.1:7897）截走绕去（可能境外）节点中转 → 慢/超时。
        # ELYS 是公网 IP、直达即可（浏览器对国内 IP 本就直连，故浏览器快）。trust_env=False 同时
        # 屏蔽环境变量代理 + Windows 系统代理；显式清 proxies 双保险。
        self._session.trust_env = False
        self._session.proxies = {}
        self._token: str | None = None

    # ---------- auth ----------
    def login(self) -> str:
        r = self._session.post(
            f"{self.base_url}/auth/login",
            json={"username": self.username, "password": self.password},
            timeout=self.timeout,
        )
        _raise_for_status(r)
        self._token = r.json()["access_token"]
        self._session.headers["Authorization"] = f"Bearer {self._token}"
        return self._token

    def _ensure_login(self):
        if not self._token:
            self.login()

    # ---------- studies ----------
    def list_studies(self) -> list[dict]:
        self._ensure_login()
        r = self._session.get(f"{self.base_url}/studies", timeout=self.timeout)
        _raise_for_status(r)
        return r.json().get("studies", [])

    def find_study_by_code(self, code: str) -> dict | None:
        """按 code 查已存在的 Study；没有返回 None。
        各调试用例靠它「认领自己的 study」做幂等：数字 study id 在测试服重置后会被回收、
        可能指到别的用例刚建的同号 study，按稳定的 code 认领才不会串台。"""
        if not code:
            return None
        for study in self.list_studies():
            if study.get("code") == code:
                return study
        return None

    # ---------- datasets ----------
    def list_datasets(self, study_id: str) -> list[dict]:
        self._ensure_login()
        r = self._session.get(
            f"{self.base_url}/studies/{study_id}/datasets",
            timeout=self.timeout,
        )
        _raise_for_status(r)
        return r.json().get("datasets", [])

    def bootstrap_dataset(
        self,
        *,
        dataset_name: str,
        dataset_code: str,
        dataset_description: str = "",
        dataset_visibility: str = "private",
        # 配对 study：默认 mode=create，新建一个 study
        study_mode: str = "create",
        study_code: str | None = None,
        study_name: str | None = None,
        study_description: str = "",
        study_id: str | None = None,       # mode=existing 时必填（12 字符 short id）
        storage_quota_gb: int = 1024,
        mount_name: str = "primary",
    ) -> dict:
        """⭐ 一次性建 Dataset 资产 + 配对 Study + 自动挂载（推荐入口）。
        POST /dataset-assets/bootstrap

        返回 dict 含: dataset_asset / dataset_version / study / mount / next_upload
        """
        self._ensure_login()
        paired_study: dict[str, Any] = {
            "mode": study_mode,
            "storage_quota_gb": storage_quota_gb,
        }
        if study_mode == "create":
            paired_study["code"] = study_code
            paired_study["name"] = study_name
            if study_description:
                paired_study["description"] = study_description
        elif study_mode == "existing":
            paired_study["study_id"] = study_id
        else:
            raise ValueError(f"study_mode 必须是 'create' 或 'existing'，传入 {study_mode!r}")

        payload = {
            "dataset": {
                "name": dataset_name,
                "code": dataset_code,
                "description": dataset_description,
                "visibility": dataset_visibility,
            },
            "paired_study": paired_study,
            "mount_name": mount_name,
        }
        r = self._session.post(
            f"{self.base_url}/dataset-assets/bootstrap",
            json=payload,
            timeout=self.timeout,
        )
        _raise_for_status(r)
        return r.json()

    def list_dataset_assets(self) -> list[dict]:
        """列出当前用户可见的所有平台级 Dataset 资产。GET /dataset-assets"""
        self._ensure_login()
        r = self._session.get(f"{self.base_url}/dataset-assets", timeout=self.timeout)
        _raise_for_status(r)
        return r.json().get("assets", [])

    def find_dataset_by_code(self, code: str) -> dict | None:
        """按 code 查已存在的 Dataset 资产；没有返回 None（用于幂等/查重）。"""
        for asset in self.list_dataset_assets():
            if asset.get("code") == code:
                return asset
        return None

    def import_recording(
        self,
        study_id: str,
        file_paths: list[str | Path],
        *,
        subject: str,
        task: str,
        dataset_asset_id: str | None = None,
        mount_name: str | None = None,
        session: str = "",
        run: str = "",
        replace_existing: bool = True,
        timeout: int = 600,
        show_progress: bool = False,
    ) -> dict:
        """同步导入一条 Recording（采集记录）。POST /studies/{study_id}/recordings/import

        file_paths: 要导入的文件。BrainVision 必须把同名的 .vhdr/.eeg/.vmrk 三件套一起传；
                    EDF/BDF/FIF 传单个文件即可。
        dataset_asset_id: 落到哪个 Dataset 资产（一般填 bootstrap 拿到的 dataset_id）；
                          不填则后端落到当前 study 的默认 working 资产。
        replace_existing: 同 subject/session/task/run 已存在时 True=作为新版本导入、False=409；
                          调试脚本建议保持 True，方便重跑。
        show_progress: True 时在终端实时画「上传进度条 + 服务器转换计时」。这个端点是同步的——
                       POST 要等后端把 BrainVision 转成 FIF 才返回，上传到 100% 后还会干等一段，
                       计时器就是让你看出「在转换、没死」。

        返回 {message, recording}，recording 里带转换后的
        n_channels / sfreq / duration_seconds / n_events 等元信息。
        """
        self._ensure_login()
        text_fields = {
            "subject": subject,
            "task": task,
            "session": session,
            "run": run,
            "replace_existing": str(replace_existing).lower(),
        }
        if dataset_asset_id:
            text_fields["dataset_asset_id"] = dataset_asset_id
        if mount_name:
            text_fields["mount_name"] = mount_name
        file_specs = [("files", Path(p)) for p in file_paths]

        on_progress, finish_progress = self._make_upload_reporter(show_progress)
        body, content_type, content_length = _encode_multipart_stream(
            text_fields, file_specs, on_progress=on_progress
        )
        try:
            r = self._session.post(
                f"{self.data_base_url}/studies/{study_id}/recordings/import",
                data=body,
                headers={"Content-Type": content_type},   # Content-Length 由 _StreamingBody.__len__ 推出
                timeout=timeout,
            )
        finally:
            finish_progress()
        _raise_for_status(r)
        return r.json()

    @staticmethod
    def _make_upload_reporter(show_progress: bool):
        """返回 (on_progress, finish)：on_progress 在上传途中画进度条、传满后起一个后台线程
        滚动「服务器转换中… Ns」；finish 在请求返回后停掉线程、收尾打印。show_progress=False
        时两者都是空操作。"""
        if not show_progress:
            return (lambda sent, total: None), (lambda: None)

        state = {"done_at": None, "last": 0.0, "prev_sent": 0, "prev_time": time.time(), "speed": 0.0}
        stop = threading.Event()

        def _spinner():
            while not stop.wait(0.5):
                elapsed = time.time() - state["done_at"]
                sys.stdout.write(f"\r  ⏳ 已上传完，服务器转换中… {elapsed:4.0f}s   ")
                sys.stdout.flush()

        def on_progress(sent: int, total: int):
            if sent >= total:
                if state["done_at"] is None:          # 刚传满：收尾进度条 + 启动转换计时
                    state["done_at"] = time.time()
                    sys.stdout.write("\r" + " " * 72 + f"\r  ↑ 上传完成 {total / 1e6:.1f} MB (100%)\n")
                    sys.stdout.flush()
                    threading.Thread(target=_spinner, daemon=True).start()
                return
            now = time.time()
            if now - state["last"] < 0.1:             # 限流：最多每 0.1s 重画一次
                return
            state["last"] = now
            # 实时网速：相邻两次回调的「字节增量 / 时间增量」，指数平滑后读数更稳
            dt = now - state["prev_time"]
            if dt > 0:
                inst = (sent - state["prev_sent"]) / dt
                if inst >= 0:
                    state["speed"] = inst if state["speed"] <= 0 else state["speed"] * 0.6 + inst * 0.4
            state["prev_time"] = now
            state["prev_sent"] = sent
            width = 24
            filled = int(width * sent / total)
            bar = "█" * filled + "·" * (width - filled)
            sys.stdout.write(
                f"\r  ↑ [{bar}] {sent / 1e6:5.1f}/{total / 1e6:.1f} MB {sent / total * 100:5.1f}%"
                f"  {_format_speed(state['speed'])}   "
            )
            sys.stdout.flush()

        def finish():
            stop.set()
            if state["done_at"] is not None:
                elapsed = time.time() - state["done_at"]
                sys.stdout.write(f"\r  ✓ 服务器处理完成，转换耗时 {elapsed:.0f}s            \n")
                sys.stdout.flush()

        return on_progress, finish

    @staticmethod
    def _make_upload_bar(show_progress: bool):
        """画上传进度条 + 字节传满后的「等待服务器接收」实时计时。返回 (on_progress, finish)。

        异步上传用。进度条到 100% 只表示字节已全部交给本地 socket/代理；之后 POST 仍阻塞着
        等代理/网络把整个 body 送达远端、服务端入队并返回 task_id——这段「最后一公里」可能不短
        （挂本地代理 clash 等时尤其明显），主线程卡在 post() 里没法刷新，于是起一个后台线程把
        等待秒数滚出来，避免看起来卡死。finish 在 post() 返回后停掉线程并收尾。
        show_progress=False 时两者都是空操作。
        """
        if not show_progress:
            return (lambda sent, total: None), (lambda: None)

        # 用足够长的空白清行：中文每字占 2 列但算 1 字符，普通空格盖不满进度条残影
        clear = "\r" + " " * 72 + "\r"
        state = {
            "last": 0.0, "done": False, "prev_sent": 0, "prev_time": time.time(), "speed": 0.0,
            "sent_at": None, "total": 0,
        }
        stop = threading.Event()

        def _waiting_spinner():
            while not stop.wait(0.5):
                elapsed = time.time() - state["sent_at"]
                sys.stdout.write(
                    f"\r  ⏳ 数据已发出 {state['total'] / 1e6:.1f} MB，等待服务器接收并入队… {elapsed:4.0f}s   "
                )
                sys.stdout.flush()

        def on_progress(sent: int, total: int):
            if state["done"]:                       # 传满后任何回调都不再重绘，杜绝 100% 后再冒 99.9%
                return
            if sent >= total:
                state["done"] = True
                state["sent_at"] = time.time()
                state["total"] = total
                sys.stdout.write(
                    f"{clear}  ⏳ 数据已发出 {total / 1e6:.1f} MB，等待服务器接收并入队…    "
                )
                sys.stdout.flush()
                threading.Thread(target=_waiting_spinner, daemon=True).start()
                return
            now = time.time()
            if now - state["last"] < 0.1:
                return
            state["last"] = now
            # 实时网速：相邻两次回调的「字节增量 / 时间增量」，指数平滑后读数更稳
            dt = now - state["prev_time"]
            if dt > 0:
                inst = (sent - state["prev_sent"]) / dt
                if inst >= 0:
                    state["speed"] = inst if state["speed"] <= 0 else state["speed"] * 0.6 + inst * 0.4
            state["prev_time"] = now
            state["prev_sent"] = sent
            width = 24
            filled = int(width * sent / total)
            bar = "█" * filled + "·" * (width - filled)
            sys.stdout.write(
                f"\r  ↑ [{bar}] {sent / 1e6:5.1f}/{total / 1e6:.1f} MB {sent / total * 100:5.1f}%"
                f"  {_format_speed(state['speed'])}   "
            )
            sys.stdout.flush()

        def finish():
            stop.set()
            if state["sent_at"] is not None:
                elapsed = time.time() - state["sent_at"]
                sys.stdout.write(
                    f"{clear}  ↑ 数据已发出 {state['total'] / 1e6:.1f} MB，服务器已接收（耗时 {elapsed:.0f}s）\n"
                )
                sys.stdout.flush()

        return on_progress, finish

    @staticmethod
    def _latest_task_message(task: dict) -> str:
        """从任务详情里取最近一条事件消息（轮询时给用户看「转换中…」这类阶段提示）。"""
        for event in reversed(task.get("events") or []):
            if event.get("message"):
                return event["message"]
        errors = (task.get("error_json") or {}).get("errors") or []
        if errors:
            return errors[0].get("message", "")
        return ""

    def import_recordings_batch_async(
        self,
        study_id: str,
        file_paths: list["Path"],
        *,
        dataset_asset_id: str | None = None,
        mount_name: str | None = None,
        session: str = "",
        run: str = "",
        replace_existing: bool = False,
        show_progress: bool = True,
    ) -> dict:
        """批量上传：一次请求传所有 EDF，从文件名解析 BIDS，返回每文件的 task_id。

        POST /recordings/import-batch-async
        返回 {results: [{filename, task_id, status, message}], n_submitted, n_skipped, n_error}
        调用方再对每个 task_id 调 wait_import_task() 等转换完成。
        """
        self._ensure_login()
        fields: list[tuple[str, str]] = []
        if dataset_asset_id:
            fields.append(("dataset_asset_id", dataset_asset_id))
        if mount_name:
            fields.append(("mount_name", mount_name))
        if session:
            fields.append(("session", session))
        if run:
            fields.append(("run", run))
        fields.append(("replace_existing", str(replace_existing).lower()))

        text_fields = dict(fields)
        file_specs = [("files", Path(p)) for p in file_paths]

        total_bytes = sum(Path(p).stat().st_size for p in file_paths)
        if show_progress:
            print(f"  ↑ 批量上传 {len(file_paths)} 个文件  共 {total_bytes / 1024 / 1024:.1f} MB")

        on_progress, finish_upload = self._make_upload_bar(show_progress)
        body, content_type, _ = _encode_multipart_stream(text_fields, file_specs, on_progress=on_progress)
        try:
            r = self._session.post(
                f"{self.data_base_url}/studies/{study_id}/recordings/import-batch-async",
                data=body,
                headers={"Content-Type": content_type},
                timeout=self.timeout,
            )
        finally:
            finish_upload()
        _raise_for_status(r)
        return r.json()

    def import_recording_async(
        self,
        study_id: str,
        file_paths: list[str | Path],
        *,
        subject: str,
        task: str,
        dataset_asset_id: str | None = None,
        mount_name: str | None = None,
        session: str = "",
        run: str = "",
        replace_existing: bool = True,
        show_progress: bool = False,
        wait: bool = True,
        poll_interval: float = 2.0,
        poll_timeout: float = 1800,
    ) -> dict:
        """异步导入：流式上传文件 → **秒拿 task_id** → 视 wait 决定是否轮询。

        wait=True（默认）：轮询至 succeeded/failed，行为与旧版完全一致。
        wait=False：上传完立刻返回 {"id": task_id, "status": "pending"}，由调用方自行调
                    wait_import_task() 批量等完成——适合「批量提交 → 集中等待」场景。
        """
        self._ensure_login()
        text_fields = {
            "subject": subject,
            "task": task,
            "session": session,
            "run": run,
            "replace_existing": str(replace_existing).lower(),
        }
        if dataset_asset_id:
            text_fields["dataset_asset_id"] = dataset_asset_id
        if mount_name:
            text_fields["mount_name"] = mount_name
        file_specs = [("files", Path(p)) for p in file_paths]

        on_progress, finish_upload = self._make_upload_bar(show_progress)
        body, content_type, content_length = _encode_multipart_stream(
            text_fields, file_specs, on_progress=on_progress
        )
        try:
            r = self._session.post(
                f"{self.data_base_url}/studies/{study_id}/recordings/import-async",
                data=body,
                headers={"Content-Type": content_type},
                timeout=self.timeout,
            )
        finally:
            finish_upload()
        _raise_for_status(r)
        task_resp = r.json()
        task_id = task_resp.get("id")
        if not task_id:
            raise ElysAPIError(r)

        if not wait:
            if show_progress:
                print(f"  ⏳ 已入队 task={task_id[:8]}…（fire-and-forget）")
            return {"id": task_id, "status": "pending"}

        if show_progress:
            print(f"  ⏳ 已入队 task={task_id[:8]}…，服务器转换中（轮询进度）")
        return self.wait_import_task(
            study_id, task_id,
            show_progress=show_progress,
            poll_interval=poll_interval,
            poll_timeout=poll_timeout,
        )

    def wait_import_task(
        self,
        study_id: str,
        task_id: str,
        *,
        show_progress: bool = False,
        poll_interval: float = 2.0,
        poll_timeout: float = 1800,
    ) -> dict:
        """轮询单个导入任务直到 succeeded/failed/canceled。
        配合 import_recording_async(wait=False) 用于「批量提交 → 集中等待」场景。
        """
        start_poll = time.time()
        deadline = start_poll + poll_timeout
        last_line = ""
        last_print_time = start_poll
        HEARTBEAT_SEC = 10
        while True:
            s = self._session.get(
                f"{self.base_url}/studies/{study_id}/tasks/{task_id}",
                timeout=self.timeout,
            )
            _raise_for_status(s)
            t = s.json()
            status = t.get("status")
            now = time.time()
            if show_progress:
                progress = float(t.get("progress") or 0)
                line = f"  ⏳ [{status}] {progress:5.1f}%  {self._latest_task_message(t)}"
                if line != last_line:
                    print(line)
                    last_line = line
                    last_print_time = now
                elif now - last_print_time >= HEARTBEAT_SEC:
                    elapsed = now - start_poll
                    print(f"  ⏳ [{status}] 等待中… {elapsed:.0f}s")
                    last_print_time = now
            if status in ("succeeded", "failed", "canceled"):
                return t
            if now > deadline:
                raise TimeoutError(f"导入任务 {task_id} 未在 {poll_timeout}s 内完成（最后状态 {status}）")
            time.sleep(poll_interval)

    # ---------- node specs ----------
    def list_node_types(self) -> set[str]:
        """返回后端当前已注册的全部节点类型字符串集合。
        用于在构建 pipeline 之前预检某个节点是否已部署，避免 validation 硬崩。"""
        self._ensure_login()
        r = self._session.get(f"{self.base_url}/pipeline/nodes", timeout=self.timeout)
        _raise_for_status(r)
        return {node.get("type", "") for node in r.json().get("nodes", [])}

    # ---------- pipelines ----------
    def list_pipelines(self, study_id: str) -> list[dict]:
        self._ensure_login()
        r = self._session.get(
            f"{self.base_url}/studies/{study_id}/pipelines",
            timeout=self.timeout,
        )
        _raise_for_status(r)
        return r.json().get("pipelines", [])

    def get_pipeline(self, study_id: str, pipeline_id: int | str) -> dict:
        self._ensure_login()
        r = self._session.get(
            f"{self.base_url}/studies/{study_id}/pipelines/{pipeline_id}",
            timeout=self.timeout,
        )
        _raise_for_status(r)
        return r.json()

    def create_pipeline(
        self,
        study_id: str,
        name: str,
        definition: dict,
        description: str = "",
    ) -> dict:
        """definition: {"graph": {"nodes": [...], "links": [...]}}"""
        self._ensure_login()
        r = self._session.post(
            f"{self.base_url}/studies/{study_id}/pipelines",
            json={
                "name": name,
                "description": description,
                "definition_json": definition,
                "enabled": True,
            },
            timeout=self.timeout,
        )
        _raise_for_status(r)
        return r.json()

    def update_pipeline(
        self,
        study_id: str,
        pipeline_id: int | str,
        *,
        definition: dict | None = None,
        name: str | None = None,
    ) -> dict:
        self._ensure_login()
        payload: dict[str, Any] = {}
        if definition is not None:
            payload["definition_json"] = definition
        if name is not None:
            payload["name"] = name
        r = self._session.put(
            f"{self.base_url}/studies/{study_id}/pipelines/{pipeline_id}",
            json=payload,
            timeout=self.timeout,
        )
        _raise_for_status(r)
        return r.json()

    def delete_pipeline(self, study_id: str, pipeline_id: int | str) -> None:
        self._ensure_login()
        r = self._session.delete(
            f"{self.base_url}/studies/{study_id}/pipelines/{pipeline_id}",
            timeout=self.timeout,
        )
        _raise_for_status(r)

    def validate(self, study_id: str, pipeline_id: int | str) -> dict:
        self._ensure_login()
        r = self._session.post(
            f"{self.base_url}/studies/{study_id}/pipelines/{pipeline_id}/validate",
            timeout=self.timeout,
        )
        _raise_for_status(r)
        return r.json()

    # ---------- runs ----------
    def trigger_run(self, study_id: str, pipeline_id: int | str, trigger: str = "manual") -> dict:
        self._ensure_login()
        r = self._session.post(
            f"{self.base_url}/studies/{study_id}/pipelines/{pipeline_id}/executions",
            json={"trigger": trigger},
            timeout=180,  # 触发请求本身可能要 10-30s（校验 + 拷快照 + 排队）
        )
        _raise_for_status(r)
        return r.json()

    def get_run(self, study_id: str, run_id: str) -> dict:
        self._ensure_login()
        r = self._session.get(
            f"{self.base_url}/studies/{study_id}/pipeline-executions/{run_id}",
            timeout=self.timeout,
        )
        _raise_for_status(r)
        return r.json()

    def list_run_nodes(self, study_id: str, run_id: str) -> list[dict]:
        self._ensure_login()
        r = self._session.get(
            f"{self.base_url}/studies/{study_id}/pipeline-executions/{run_id}/jobs",
            timeout=self.timeout,
        )
        _raise_for_status(r)
        return r.json().get("jobs", [])

    def wait_run(
        self,
        study_id: str,
        run_id: str,
        *,
        poll_sec: float = 2.0,
        timeout_sec: float = 900,
        on_status_change=None,
    ) -> dict:
        deadline = time.time() + timeout_sec
        last_status = None
        while time.time() < deadline:
            run = self.get_run(study_id, run_id)
            status = run.get("status")
            if status != last_status:
                if on_status_change:
                    on_status_change(status, run)
                else:
                    print(f"  [run {run_id[:8]}] status -> {status}")
                last_status = status
            if status in ("completed", "failed", "canceled"):
                return run
            time.sleep(poll_sec)
        raise TimeoutError(f"run {run_id} 未在 {timeout_sec}s 内完成（最后 {last_status}）")

    # ---------- derived datasets / artifacts ----------
    def list_run_derived(self, study_id: str, run_id: str) -> list[dict]:
        # 没有独立的 per-execution 派生列表端点；执行详情(GET pipeline-executions/{id})里就带 study_outputs
        self._ensure_login()
        r = self._session.get(
            f"{self.base_url}/studies/{study_id}/pipeline-executions/{run_id}",
            timeout=self.timeout,
        )
        _raise_for_status(r)
        return r.json().get("study_outputs", [])

    def download_derived(self, study_id: str, dataset_id: str, out_path: str | Path) -> Path:
        self._ensure_login()
        r = self._session.get(
            f"{self.data_base_url}/studies/{study_id}/outputs/{dataset_id}/download",
            stream=True,
            timeout=600,
        )
        _raise_for_status(r)
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
        return out

    # ---------- LoadData 元信息（看 ch_names / event_labels）----------
    def resolve_load_data(self, study_id: str, dataset_ids: list[str]) -> dict:
        self._ensure_login()
        r = self._session.post(
            f"{self.base_url}/studies/{study_id}/pipeline/load-data/resolve",
            json={
                "selection_mode": "explicit",
                "dataset_ids": dataset_ids,
                "dataset_filter": {},
            },
            timeout=self.timeout,
        )
        _raise_for_status(r)
        return r.json()
