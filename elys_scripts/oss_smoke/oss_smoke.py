#!/usr/bin/env python3
"""
ELYS OSS 冒烟 / 初始化自检脚本（独立，不依赖 ELYS 后端代码）。

Purpose: 在本地或计算服务器上，验证「凭证 / endpoint / 桶 / 权限」四件事是否全部打通，
         为后续把 ELYS 存储后端切到阿里云 OSS 做前置验证。
Related: 日志/12_OSS存储迁移260621/00_OSS存储迁移改造清单.md（这是 OSS-1/OSS-4 之前的网络+权限验证）。

只依赖 oss2，做一轮「写 → 读 → 查 → 列 → 删」的最小闭环，每步独立报 [OK]/[FAIL]，
最后给总结。测试态默认用完即删，桶保持干净（与控制台「0 文件」一致）。

------------------------------------------------------------------------------
用法 A —— 本机 Windows，走【公网】endpoint（laptop 只能走公网）：
    pip install oss2
    # PowerShell:
    $env:OSS_AK="LTAI..."; $env:OSS_SK="..."; python oss_smoke.py --where local

用法 B —— 计算服务器上，走【内网】endpoint（内网只能在同地域 ECS 上通）：
    OSS_AK=... OSS_SK=... python3 oss_smoke.py --where compute
    # 或用同目录的 run_oss_smoke_remote.ps1 从 Windows 一键远程跑（推荐）
------------------------------------------------------------------------------

凭证只从环境变量读，绝不写进脚本 / 仓库：
    OSS_AK / OSS_SK（兼容别名 OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET）

退出码：全部通过 = 0；任一步失败 = 1（远程包装器据此判成败）。
"""
from __future__ import annotations

import argparse
import os
import sys

# Windows 控制台默认可能是 GBK，强制 stdout/stderr 走 UTF-8，避免中文/特殊字符崩在 print。
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass


def _need_oss2():
    try:
        import oss2  # noqa: PLC0415
        return oss2
    except ImportError:
        print("[FAIL] 没装 oss2。先装依赖：  pip install oss2")
        sys.exit(1)


def _mask(secret: str) -> str:
    """脱敏：只露头 4 尾 3，中间打码，防止 AccessKey 进日志/截图。"""
    if not secret:
        return "(空)"
    if len(secret) <= 8:
        return secret[0] + "***"
    return f"{secret[:4]}...{secret[-3:]}"


def _cred_problems(ak: str, sk: str) -> list[str]:
    """开跑前先给凭证体检：非 ASCII / 残留占位符 是最常见的低级错（直接粘了示例文本）。
    真实 AccessKey 是纯英文数字（AK 形如 LTAI5t...，SK 约 30 位），含中文必是占位符。"""
    problems: list[str] = []
    for name, val in (("OSS_AK", ak), ("OSS_SK", sk)):
        try:
            val.encode("ascii")
        except UnicodeEncodeError:
            problems.append(f"{name} 含非 ASCII 字符 —— 八成把示例占位符（如 'LTAI你的Key'）直接粘进来了")
    if "你的" in ak or "你的" in sk:
        problems.append("凭证里还残留示例占位符『你的...』，请换成真实 AccessKey")
    return problems


# 仓库之外的明文凭证文件（用户目录下，git 看不到）。存一次，以后自动读。
_CRED_FILE = os.path.join(os.path.expanduser("~"), ".elys", "oss.env")


def _read_cred_file() -> tuple[str, str]:
    """从 ~/.elys/oss.env 读 OSS_AK / OSS_SK（KEY=VALUE 格式，# 开头是注释）。"""
    if not os.path.exists(_CRED_FILE):
        return "", ""
    ak = sk = ""
    try:
        with open(_CRED_FILE, encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip().upper()
                val = val.strip().strip('"').strip("'")
                if key in ("OSS_AK", "OSS_ACCESS_KEY_ID"):
                    ak = val
                elif key in ("OSS_SK", "OSS_ACCESS_KEY_SECRET"):
                    sk = val
    except OSError:
        pass
    return ak, sk


def _read_windows_user_env(name: str) -> str:
    """直接读 Windows 用户级环境变量（注册表 HKCU\\Environment）。
    绕开『当前终端是旧进程、SetEnvironmentVariable 设的新值它看不到』的坑——
    这正是反复要你“开新终端”的根源。非 Windows 返回空。"""
    if os.name != "nt":
        return ""
    try:
        import winreg  # noqa: PLC0415
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            val, _ = winreg.QueryValueEx(key, name)
            return str(val).strip()
    except (FileNotFoundError, OSError, ImportError):
        return ""


def _read_credentials() -> tuple[str, str]:
    """凭证来源优先级：① 当前进程环境变量 → ② Windows 用户级环境变量(注册表,免开新终端)
    → ③ 仓库外明文文件 ~/.elys/oss.env → ④ 当场粘贴兜底。"""
    ak = (os.environ.get("OSS_AK") or os.environ.get("OSS_ACCESS_KEY_ID") or "").strip()
    sk = (os.environ.get("OSS_SK") or os.environ.get("OSS_ACCESS_KEY_SECRET") or "").strip()
    if ak and sk and not _cred_problems(ak, sk):
        return ak, sk
    rak = (_read_windows_user_env("OSS_AK") or _read_windows_user_env("OSS_ACCESS_KEY_ID")).strip()
    rsk = (_read_windows_user_env("OSS_SK") or _read_windows_user_env("OSS_ACCESS_KEY_SECRET")).strip()
    if rak and rsk and not _cred_problems(rak, rsk):
        print("[i] 用 Windows 用户级环境变量（注册表，无需新开终端）")
        return rak, rsk
    fak, fsk = _read_cred_file()
    if fak and fsk and not _cred_problems(fak, fsk):
        print(f"[i] 用凭证文件 {_CRED_FILE}")
        return fak, fsk
    print(f"[i] 没找到可用凭证（环境变量 / 注册表 / {_CRED_FILE} 都没有或仍是占位符）→ 现在直接粘贴：")
    import getpass  # noqa: PLC0415
    try:
        ak = input("    AccessKey ID（LTAI 开头，粘贴后按回车）: ").strip()
        sk = getpass.getpass("    AccessKey Secret（粘贴后按回车，输入时不显示）: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n[FAIL] 已取消输入。")
    return ak, sk


def _profile_oss_default(key: str, fallback: str) -> str:
    """OSS_BUCKET / OSS_REGION 默认值：env > deploy profile（默认 aliyun-test）> fallback。
    与 deploy/clear_oss 同一份单一事实源；本地手动跑也跟随 profile，不必每次 --bucket。"""
    env_val = os.environ.get(key)
    if env_val and env_val.strip():
        return env_val.strip()
    profile = os.environ.get("ELYS_DEPLOY_PROFILE", "aliyun-test")
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    path = os.path.join(root, "elys_project", "deploy", "profiles", f"{profile}.env")
    values = {}
    try:
        with open(path, encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                values[k.strip().upper()] = v.strip().strip('"').strip("'")
    except OSError:
        return fallback
    # OSS_BUCKET 跟随 ACTIVE_SET（部署资源集）：${ACTIVE}_OSS_BUCKET 优先；OSS_REGION 等共享键直接取。
    active = (values.get("ACTIVE_SET") or "").strip()
    if key == "OSS_BUCKET" and active:
        set_bucket = values.get(active.upper() + "_OSS_BUCKET")
        if set_bucket:
            return set_bucket
    return values.get(key) or fallback


def _resolve_endpoint(args) -> str:
    if args.endpoint:
        ep = args.endpoint
    elif args.where == "compute":
        ep = f"oss-{args.region}-internal.aliyuncs.com"   # ECS 内网（同地域免费 + 快）
    else:
        ep = f"oss-{args.region}.aliyuncs.com"            # 公网（laptop 测通用，计流量费）
    if not ep.startswith(("http://", "https://")):
        ep = "https://" + ep
    return ep


def _describe_oss_error(exc) -> str:
    """把 oss2 异常拆成 HTTP 状态 / 错误码 / request_id / 消息，便于贴给客服或排错。"""
    bits = []
    status = getattr(exc, "status", None)
    code = getattr(exc, "code", None)
    request_id = getattr(exc, "request_id", None)
    message = getattr(exc, "message", None) or str(exc)
    if status is not None:
        bits.append(f"HTTP {status}")
    if code:
        bits.append(f"code={code}")
    if request_id:
        bits.append(f"request_id={request_id}")
    bits.append(message)
    return " | ".join(b for b in bits if b)


def _connect_hints(oss2, exc, endpoint: str) -> list[str]:
    """根据异常类型给出"人话"排错建议。"""
    hints: list[str] = []
    code = (getattr(exc, "code", "") or "").lower()
    msg = (getattr(exc, "message", "") or str(exc)).lower()

    if isinstance(exc, oss2.exceptions.RequestError):
        # 连不上：DNS 解析不了 / 网络超时
        if "-internal" in endpoint:
            hints.append("用的是【内网】endpoint，但本机不在阿里云同地域 ECS 上 → 内网域名解析不到。")
            hints.append("本机自测请改 --where local（公网）；内网只能在计算服务器上验（用 run_oss_smoke_remote.ps1）。")
        else:
            hints.append("网络连不上 OSS：检查本机能否上外网 / 是否被代理拦截 / endpoint 拼写。")
    elif "invalidaccesskeyid" in code or "invalidaccesskeyid" in msg:
        hints.append("AccessKey ID 不对（OSS_AK）：确认是 RAM 用户的 AccessKey，没多空格。")
    elif "signaturedoesnotmatch" in code or "signaturedoesnotmatch" in msg:
        hints.append("AccessKey Secret 不对（OSS_SK）：八成是复制时漏字符 / 多空格。")
    elif "nosuchbucket" in code or "nosuchbucket" in msg:
        hints.append("桶名不对或不存在：确认 --bucket 与控制台一致。")
    elif "accessdenied" in code or "accessdenied" in msg:
        if "endpoint" in msg or "region" in msg or "location" in msg:
            hints.append("地域/endpoint 对不上：桶在某地域，但 endpoint 指向别的地域 → 检查 --region。")
        else:
            hints.append("权限不足：当前 RAM 用户没有该操作权限 → 给它授 AliyunOSSFullAccess（测试期）或放宽桶策略。")
    return hints


def _run_step(name: str, fn, results: list) -> bool:
    """跑一步：成功记 [OK]，抛错记 [FAIL] 并打印诊断。返回是否成功。"""
    try:
        detail = fn()
        print(f"  [OK]   {name}" + (f"  —  {detail}" if detail else ""))
        results.append((name, True))
        return True
    except Exception as exc:  # noqa: BLE001 — 冒烟脚本要尽量收集每步结果，不中断
        print(f"  [FAIL] {name}  —  {exc.__class__.__name__}: {exc}")
        results.append((name, False))
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="ELYS OSS 冒烟/初始化自检")
    parser.add_argument("--bucket", default=_profile_oss_default("OSS_BUCKET", "elys-oss-test1"),
                        help="桶名（默认从 profile OSS_BUCKET 读，回落 elys-oss-test1）")
    parser.add_argument("--region", default=_profile_oss_default("OSS_REGION", "cn-shenzhen"),
                        help="地域 RegionId（默认从 profile OSS_REGION 读，回落 cn-shenzhen）")
    parser.add_argument("--where", choices=["local", "compute"], default="local",
                        help="local=公网 endpoint（本机自测）；compute=内网 endpoint（计算服务器上）")
    parser.add_argument("--endpoint", default="", help="直接指定完整 endpoint（覆盖 --where/--region）")
    parser.add_argument("--keep", action="store_true", help="保留测试对象不删（默认用完即删）")
    args = parser.parse_args()

    oss2 = _need_oss2()

    ak, sk = _read_credentials()
    problems = _cred_problems(ak, sk)
    if problems:
        print("[FAIL] 凭证仍然不对：")
        for p in problems:
            print(f"       - {p}")
        print("       去阿里云控制台『RAM 访问控制』拿真实 AccessKey（纯英文数字），别再用示例占位符。")
        return 1

    endpoint = _resolve_endpoint(args)
    test_key = f"__elys_smoke__/probe-{os.getpid()}.txt"
    payload = b"elys oss smoke test :: do not keep\n"

    print("=" * 70)
    print(" ELYS OSS 冒烟 / 初始化自检")
    print("-" * 70)
    print(f"  桶 bucket     : {args.bucket}")
    print(f"  地域 region   : {args.region}")
    print(f"  endpoint      : {endpoint}   ({'内网' if '-internal' in endpoint else '公网'})")
    print(f"  AccessKey     : {_mask(ak)}")
    print(f"  测试对象 key  : {test_key}")
    print("=" * 70)

    auth = oss2.Auth(ak, sk)
    bucket = oss2.Bucket(auth, endpoint, args.bucket)

    # ---- 步骤 0：连接 + 鉴权探测（最先暴露 DNS/地域/凭证问题）----
    try:
        info = bucket.get_bucket_info()
        loc = getattr(info, "location", "?")
        storage = getattr(info, "storage_class", "?")
        print(f"  [OK]   连接/鉴权探测  —  location={loc}  storage_class={storage}")
    except oss2.exceptions.AccessDenied:
        # 连接是通的，只是 RAM 用户没 GetBucketInfo 权限 —— 不致命，继续做读写测试。
        print("  [i]    连接/鉴权 OK，但当前 RAM 用户无 GetBucketInfo 权限（不影响读写，继续）")
    except Exception as exc:  # noqa: BLE001
        print(f"  [FAIL] 连接/鉴权探测  —  {_describe_oss_error(exc)}")
        for h in _connect_hints(oss2, exc, endpoint):
            print(f"         ↳ {h}")
        print("\n连接都没通，后面不用测了。修好上面的问题再跑。")
        return 1

    # ---- 步骤 1~5：写 → 读 → 查 → 列 → 删，每步独立报告（能精确暴露 RAM 策略缺哪个权限）----
    results: list = []

    def step_put():
        bucket.put_object(test_key, payload)
        return f"已写入 {len(payload)} 字节 (PutObject)"

    def step_get():
        got = bucket.get_object(test_key).read()
        if got != payload:
            raise ValueError("读回内容与写入不一致")
        return "读回一致 (GetObject)"

    def step_head():
        if not bucket.object_exists(test_key):
            raise ValueError("object_exists 返回 False")
        return "对象存在 (HeadObject)"

    def step_list():
        keys = [o.key for o in oss2.ObjectIterator(bucket, prefix="__elys_smoke__/", max_keys=10)]
        return f"列出 {len(keys)} 个对象 (ListObjects)"

    _run_step("写 PutObject", step_put, results)
    _run_step("读 GetObject", step_get, results)
    _run_step("查 HeadObject", step_head, results)
    _run_step("列 ListObjects", step_list, results)

    if args.keep:
        print("  [i]    --keep：保留测试对象，未删除")
    else:
        _run_step("删 DeleteObject", lambda: (bucket.delete_object(test_key), "已清理")[1], results)

    # ---- 总结 ----
    print("-" * 70)
    n_ok = sum(1 for _, ok in results if ok)
    n_total = len(results)
    all_ok = n_ok == n_total
    print(f"  结果：{n_ok}/{n_total} 步通过")
    if all_ok:
        print("  [PASS] 凭证 / endpoint / 桶 / 权限 全部打通。可以放心进 OSS-1/OSS-4 接后端了。")
    else:
        failed = [name for name, ok in results if not ok]
        print(f"  [FAIL] 未通过：{', '.join(failed)}")
        print("         多半是 RAM 策略漏了对应权限 —— 测试期直接授 AliyunOSSFullAccess 最省事。")
    print("=" * 70)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
