#!/usr/bin/env python3
"""Clear the OSS test bucket on deploy (debug phase: initialize OSS alongside the local RESET).

Runs locally before deploy (called from s2_deploy.cmd). NON-INTERACTIVE and BEST-EFFORT:
no credentials / oss2 missing / network error -> print and skip; NEVER fails the deploy (exit 0).

SAFETY GATE: only clears when the active deploy profile has RESET_STORAGE=true (and not
KEEP_EXISTING_DATA) -- i.e. exactly when the deploy also wipes local storage. A production
profile (RESET_STORAGE=false) is left untouched, so this can't become a prod data-loss footgun.

Credentials (non-interactive): env vars -> Windows user registry -> ~/.elys/oss.env.
ASCII-only output (runs in a GBK cmd console).
"""
from __future__ import annotations

import os
import sys

BUCKET = (os.environ.get("OSS_BUCKET") or "elys-oss-test1").strip()
REGION = (os.environ.get("OSS_REGION") or "cn-shenzhen").strip()
ENDPOINT = f"https://oss-{REGION}.aliyuncs.com"  # local clear goes over the public endpoint


def _repo_root() -> str:
    # clear_oss.py is at <repo>/elys_scripts/oss_smoke/ -> up 2 levels
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _profile_name(argv: list[str]) -> str:
    for i, tok in enumerate(argv):
        low = tok.lower()
        if low in ("-profile", "--profile") and i + 1 < len(argv):
            return argv[i + 1].strip()
        if low.startswith("-profile=") or low.startswith("--profile="):
            return tok.split("=", 1)[1].strip()
    return (os.environ.get("ELYS_DEPLOY_PROFILE") or "aliyun-test").strip()


def _read_env_file(path: str) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                values[key.strip().upper()] = val.strip().strip('"').strip("'")
    except OSError:
        pass
    return values


def _winreg_user_env(name: str) -> str:
    if os.name != "nt":
        return ""
    try:
        import winreg  # noqa: PLC0415
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            val, _ = winreg.QueryValueEx(key, name)
            return str(val).strip()
    except (FileNotFoundError, OSError, ImportError):
        return ""


def _resolve_cred(*names: str) -> str:
    for n in names:
        v = os.environ.get(n)
        if v and v.strip():
            return v.strip()
    for n in names:
        v = _winreg_user_env(n)
        if v:
            return v
    cred = _read_env_file(os.path.join(os.path.expanduser("~"), ".elys", "oss.env"))
    for n in names:
        if cred.get(n):
            return cred[n]
    return ""


def _is_placeholder(v: str) -> bool:
    if not v:
        return True
    try:
        v.encode("ascii")
    except UnicodeEncodeError:
        return True
    return "你的" in v  # 含"你的"占位符


def main() -> int:
    # ---- safety gate: only when this deploy also resets local storage ----
    profile = _profile_name(sys.argv[1:])
    profile_path = os.path.join(_repo_root(), "elys_project", "deploy", "profiles", f"{profile}.env")
    prof = _read_env_file(profile_path)
    reset_storage = (prof.get("RESET_STORAGE", "") or "").lower() == "true"
    keep = (prof.get("KEEP_EXISTING_DATA", "") or "").lower() == "true"
    if not reset_storage or keep:
        print(f"[clear_oss] profile '{profile}' is not a reset deploy (RESET_STORAGE!=true) -> skip OSS clear.")
        return 0

    ak = _resolve_cred("OSS_AK", "OSS_ACCESS_KEY_ID")
    sk = _resolve_cred("OSS_SK", "OSS_ACCESS_KEY_SECRET")
    if _is_placeholder(ak) or _is_placeholder(sk):
        print("[clear_oss] no usable OSS credentials -> skip OSS clear (deploy continues).")
        return 0

    try:
        import oss2  # noqa: PLC0415
    except ImportError:
        print("[clear_oss] oss2 not installed -> skip OSS clear (pip install oss2 to enable).")
        return 0

    try:
        bucket = oss2.Bucket(oss2.Auth(ak, sk), ENDPOINT, BUCKET)
        keys = [obj.key for obj in oss2.ObjectIterator(bucket)]
        if not keys:
            print(f"[clear_oss] bucket '{BUCKET}' already empty.")
            return 0
        deleted = 0
        for i in range(0, len(keys), 1000):
            batch = keys[i:i + 1000]
            bucket.batch_delete_objects(batch)
            deleted += len(batch)
        print(f"[clear_oss] cleared bucket '{BUCKET}': deleted {deleted} objects.")
        return 0
    except Exception as exc:  # noqa: BLE001 — best-effort: never block deploy
        print(f"[clear_oss] clear error (skipped, deploy continues): {exc.__class__.__name__}: {exc}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
