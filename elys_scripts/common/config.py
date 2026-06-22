"""
所有项目共享的默认账号 / 地址。
每个项目可以在自己的 config_local.py 里覆盖 STUDY_ID 等。

服务器地址默认从【部署 profile】读取，做到单一数据源：
  elys_project/deploy/profiles/<profile>.env 里的 ENTRY_SERVER_IP / COMPUTE_SERVER_IP
部署时改了 IP（尤其是经常变的计算服），这些调试脚本会自动跟随，不用两头改。

优先级（IP）：环境变量 > 部署 profile；脚本内不设 IP 默认，两者都缺则直接报错（IP 单一事实源，不写死在脚本）。
  临时切某台计算服：    $env:ELYS_COMPUTE_HOST="1.2.3.4"; python run.py
  换用别的 profile：    $env:ELYS_DEPLOY_PROFILE="prod-hybrid"; python run.py

  登录 / 列表 / 建 dataset 等轻 API → BASE_URL（走入口服代理）
  文件上传 / 下载 / 大数据 API     → DATA_BASE_URL（直连计算服）
"""
from __future__ import annotations

import os
from pathlib import Path

# ---- 协议兜底（非 IP、不会过期）。服务器 IP 不设脚本内默认：只认 profile / 环境变量，缺则报错 ----
_DEFAULT_SCHEME = "http"

# 部署 profile 路径： <repo根>/elys_project/deploy/profiles/<profile>.env
# config.py 在 <repo根>/elys_scripts/common/ 下，上溯三层到 repo 根。
_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROFILE_NAME = os.environ.get("ELYS_DEPLOY_PROFILE", "aliyun-test")
_PROFILE_PATH = _REPO_ROOT / "elys_project" / "deploy" / "profiles" / f"{_PROFILE_NAME}.env"


def _read_env_file(path: Path) -> dict[str, str]:
    """极简 .env 解析：KEY=VALUE，跳过空行/注释、去掉引号。文件不存在则返回空 dict。"""
    values: dict[str, str] = {}
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key:
                values[key] = val
    except OSError:
        pass  # profile 不在/读不了 → 用兜底默认值
    return values


_profile = _read_env_file(_PROFILE_PATH)

# ACTIVE_SET（部署资源集）：把 ${ACTIVE_SET}_ENTRY_SERVER_IP/COMPUTE_SERVER_IP 解析成扁平名供下方使用。
# 留空 → 用扁平 ENTRY_SERVER_IP/COMPUTE_SERVER_IP（向后兼容，其它 profile 不受影响）。
_active_set = (_profile.get("ACTIVE_SET") or "").strip()
if _active_set:
    _set_prefix = _active_set.upper() + "_"
    for _key in ("ENTRY_SERVER_IP", "COMPUTE_SERVER_IP"):
        _set_val = _profile.get(_set_prefix + _key)
        if _set_val:
            _profile[_key] = _set_val

# ---- 最终地址：环境变量 > 部署 profile。IP 无脚本内兜底——缺就报错（单一事实源）----
_SCHEME = os.environ.get("ELYS_SCHEME") or _profile.get("PUBLIC_SCHEME") or _DEFAULT_SCHEME
ENTRY_HOST = os.environ.get("ELYS_ENTRY_HOST") or _profile.get("ENTRY_SERVER_IP")
COMPUTE_HOST = os.environ.get("ELYS_COMPUTE_HOST") or _profile.get("COMPUTE_SERVER_IP")


def _resolve_url(full_override: str | None, host: str | None, *, label: str, profile_key: str, env_key: str) -> str:
    """整条 URL 被 ELYS_*_BASE_URL 覆盖时直接返回；否则拼 scheme://host/api/v1。
    host 缺失（profile 没配 + 环境变量没设）→ 报错，指明去 profile 配（IP 单一事实源、不写死在脚本）。"""
    if full_override:
        return full_override
    if not host:
        raise RuntimeError(
            f"找不到{label}地址：请在 {_PROFILE_PATH} 配 {profile_key}=<ip>，"
            f"或设环境变量 {env_key}（IP 不写死在脚本里）。"
        )
    return f"{_SCHEME}://{host}/api/v1"


# 轻 API：入口服务器代理（登录、列 study、建 dataset 等）
BASE_URL = _resolve_url(os.environ.get("ELYS_BASE_URL"), ENTRY_HOST, label="入口服", profile_key="ENTRY_SERVER_IP", env_key="ELYS_ENTRY_HOST")

# 大数据 API：直连计算服务器（文件上传 / 下载 / 波形等）
DATA_BASE_URL = _resolve_url(os.environ.get("ELYS_DATA_BASE_URL"), COMPUTE_HOST, label="计算服", profile_key="COMPUTE_SERVER_IP", env_key="ELYS_COMPUTE_HOST")

# 浏览器登录页那一对（不是 SSH）
USERNAME = "admin"
PASSWORD = "qwer123456."
