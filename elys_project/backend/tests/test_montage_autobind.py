"""
Purpose: 单元测试 app/engine/preprocess/montage_autobind.py 的自动电极定位分流。

核心断言（按通道命名分流到正确家族的帽）：
- BioSemi 命名（A1..B32）          → family == "biosemi"，applied / has_positions
- EGI 命名（E1..E128）             → family == "egi"
- 标准 10-20 命名（Fp1/Cz..）      → family == "standard"
- 无信息命名（Ch1..Ch10）          → 不绑（applied False、has_positions False）
- 文件自带坐标                      → 保留不覆盖（family == "preexisting"、has_positions True）

需要云端锁定的 mne（本机无运行环境）；mne 不可用时整文件跳过。
Related: app/engine/preprocess/montage_autobind.py
"""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

mne = pytest.importorskip("mne")
np = pytest.importorskip("numpy")

from app.engine.preprocess.montage_autobind import autobind_montage  # noqa: E402


def _make_raw(ch_names: list[str]):
    """用给定通道名造一个最小 EEG Raw（全零数据，10 个采样点即可）。"""
    info = mne.create_info(ch_names=list(ch_names), sfreq=100.0, ch_types="eeg")
    data = np.zeros((len(ch_names), 10), dtype=float)
    return mne.io.RawArray(data, info, verbose="ERROR")


def test_biosemi_naming_binds_biosemi_cap():
    names = [f"A{i}" for i in range(1, 33)] + [f"B{i}" for i in range(1, 33)]  # 64 导 BioSemi
    raw = _make_raw(names)
    detail = autobind_montage(raw, upload_kind="bdf")
    assert detail["applied"] is True
    assert detail["has_positions"] is True
    assert detail["family"] == "biosemi"
    assert detail["montage"].startswith("biosemi")
    assert raw.get_montage() is not None


def test_egi_naming_binds_gsn_hydrocel():
    names = [f"E{i}" for i in range(1, 129)]  # 128 导 EGI HydroCel
    raw = _make_raw(names)
    detail = autobind_montage(raw, upload_kind="edf")
    assert detail["applied"] is True
    assert detail["family"] == "egi"
    assert raw.get_montage() is not None


def test_standard_1020_naming_binds_standard_cap():
    names = [
        "Fp1", "Fp2", "F7", "F3", "Fz", "F4", "F8",
        "T7", "C3", "Cz", "C4", "T8",
        "P7", "P3", "Pz", "P4", "P8", "O1", "O2",
    ]
    raw = _make_raw(names)
    detail = autobind_montage(raw, upload_kind="edf")
    assert detail["applied"] is True
    assert detail["family"] == "standard"
    assert detail["n_matched"] >= len(names) - 2  # 绝大多数通道都该落到标准帽


def test_nonstandard_naming_skips_binding():
    names = [f"Ch{i}" for i in range(1, 11)]  # 无信息命名，认不出任何帽
    raw = _make_raw(names)
    detail = autobind_montage(raw, upload_kind="edf")
    assert detail["applied"] is False
    assert detail["has_positions"] is False
    assert raw.get_montage() is None


def test_preexisting_positions_are_not_overwritten():
    names = ["Fp1", "Fp2", "Cz", "Pz", "O1", "O2"]
    raw = _make_raw(names)
    raw.set_montage(mne.channels.make_standard_montage("standard_1020"), on_missing="ignore", verbose="ERROR")
    detail = autobind_montage(raw, upload_kind="edf")
    assert detail["applied"] is False          # 没有再套模板
    assert detail["has_positions"] is True      # 但文件已带坐标
    assert detail["family"] == "preexisting"
