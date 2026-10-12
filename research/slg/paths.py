"""Repo-relative paths. research/slg/paths.py -> parents[2] is the repo root."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RESULTS = ROOT / "results"
