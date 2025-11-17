"""Centralized project path helpers."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RAW_DATA_DIR = ROOT / "raw_data"
MID_DIR = ROOT / "mid"
ANALYSIS_MID_DIR = MID_DIR / "analysis"
PCFG_MID_DIR = MID_DIR / "pcfg_advance"
PCFG_LIB_DIR = ROOT / "pcfg_advance" / "lib"
REPORT_ASSETS_DIR = ROOT / "analysis" / "report_assets"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def analysis_mid_dir(*parts: str) -> Path:
    target = ANALYSIS_MID_DIR.joinpath(*parts) if parts else ANALYSIS_MID_DIR
    return ensure_dir(target)


def pcfg_mid_dir(*parts: str) -> Path:
    target = PCFG_MID_DIR.joinpath(*parts) if parts else PCFG_MID_DIR
    return ensure_dir(target)


def report_assets_dir(*parts: str) -> Path:
    return ensure_dir(REPORT_ASSETS_DIR.joinpath(*parts))
