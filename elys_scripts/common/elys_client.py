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


def _encode_multipart_stream(
    text_fields: dict[str, str],
    file_specs: list[tuple[str, Path]],
    *,
    chunk_size: int = 256 * 1024,
    on_progress: Callable[[int, int], None] | None = None,
) -> tuple[Iterator[bytes], str, int]:
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
    return _body(), content_type, total


class ElysClient:
    def __init__(self, base_url: str, username: str, password: str, timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self._session = requests.Session()
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
                f"{self.base_url}/studies/{study_id}/recordings/import",
                data=body,
                headers={"Content-Type": content_type, "Content-Length": str(content_length)},
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

        state = {"done_at": None, "last": 0.0}
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
                    sys.stdout.write(f"\r  ↑ 上传完成 {total / 1e6:.1f} MB (100%)          \n")
                    sys.stdout.flush()
                    threading.Thread(target=_spinner, daemon=True).start()
                return
            now = time.time()
            if now - state["last"] < 0.1:             # 限流：最多每 0.1s 重画一次
                return
            state["last"] = now
            width = 24
            filled = int(width * sent / total)
            bar = "█" * filled + "·" * (width - filled)
            sys.stdout.write(
                f"\r  ↑ [{bar}] {sent / 1e6:5.1f}/{total / 1e6:.1f} MB {sent / total * 100:5.1f}%"
            )
            sys.stdout.flush()

        def finish():
            stop.set()
            if state["done_at"] is not None:
                elapsed = time.time() - state["done_at"]
                sys.stdout.write(f"\r  ✓ 服务器处理完成，转换耗时 {elapsed:.0f}s            \n")
                sys.stdout.flush()

        return on_progress, finish

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
        # 没有独立的 per-execution 派生列表端点；执行详情(GET pipeline-executions/{id})里就带 derived_datasets
        self._ensure_login()
        r = self._session.get(
            f"{self.base_url}/studies/{study_id}/pipeline-executions/{run_id}",
            timeout=self.timeout,
        )
        _raise_for_status(r)
        return r.json().get("derived_datasets", [])

    def download_derived(self, study_id: str, dataset_id: str, out_path: str | Path) -> Path:
        self._ensure_login()
        r = self._session.get(
            f"{self.base_url}/studies/{study_id}/derived-datasets/{dataset_id}/download",
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
