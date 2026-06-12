"""elys_scripts 终端 UI —— 与部署脚本 step_banner.ps1 同族的视觉语法。

细线 rule + 反色徽标(PASS/FAIL/OK) + 灰键彩值 KV 行。step3「测试」主色=绿。
底层是 ANSI 转义；Windows 老 conhost 需要先启用 VT 模式，这里在 import 时自动做。
不引第三方库（避免污染被测 venv）。
"""
from __future__ import annotations

import os
import sys

# stdout/stderr 强制 UTF-8（不依赖 PYTHONUTF8 外部变量；否则 GBK 编不出 ── / ⚠ 会崩在 print）
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ── Windows 启用 ANSI/VT（新版 Windows Terminal 默认支持；老 conhost 需显式开）──
if os.name == "nt":
    try:
        import ctypes

        _k = ctypes.windll.kernel32
        # ENABLE_PROCESSED_OUTPUT(1) | ENABLE_WRAP_AT_EOL(2) | ENABLE_VIRTUAL_TERMINAL_PROCESSING(4)
        _k.SetConsoleMode(_k.GetStdHandle(-11), 7)
    except Exception:
        pass

RESET = "\033[0m"
GRAY = "\033[90m"
WHITE = "\033[97m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"

_BG = {"green": "\033[42m", "cyan": "\033[46m", "red": "\033[41m", "yellow": "\033[43m"}


def badge(text: str, bg: str = "green", fg: str = WHITE) -> str:
    return f"{_BG.get(bg, '')}{fg} {text} {RESET}"


def rule(color: str = GREEN, width: int = 64) -> None:
    print(f"{color}  " + ("─" * width) + RESET)


def section(title: str, color: str = GREEN) -> None:
    print()
    print(f"{color}  ── {title} ──{RESET}")


def step(label: str, title: str) -> None:
    print()
    print(f"{badge(label, 'green')}  {WHITE}{title}{RESET}")


def ok(msg: str) -> None:
    print(f"{badge('OK', 'green')}  {msg}")


def fail(msg: str) -> None:
    print(f"{badge('FAIL', 'red')}  {RED}{msg}{RESET}")


def warn(msg: str) -> None:
    print(f"{YELLOW}  ⚠ {msg}{RESET}")


def info(msg: str) -> None:
    print(f"{GRAY}  {msg}{RESET}")


def kv(key: str, value: str, color: str = WHITE) -> None:
    print(f"{GRAY}  {key:<12}{RESET}{color}{value}{RESET}")


def passed(msg: str) -> None:
    """终态成功横幅。"""
    print()
    rule(GREEN)
    print(f"{badge('PASS', 'green')}  {GREEN}{msg}{RESET}")
    rule(GREEN)


def died(msg: str) -> None:
    """终态失败横幅。"""
    print()
    rule(RED)
    print(f"{badge('FAIL', 'red')}  {RED}{msg}{RESET}")
    rule(RED)
