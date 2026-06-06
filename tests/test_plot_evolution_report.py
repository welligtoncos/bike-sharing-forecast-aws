"""Testes — plot_evolution_report.py"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

pytest.importorskip("matplotlib")
pytest.importorskip("openpyxl")

from plot_evolution_report import load_report, plot_png, write_xlsx  # noqa: E402


def _sample_report() -> pd.DataFrame:
    rows = []
    for i, month in enumerate(range(1, 4)):
        rows.append(
            {
                "ref_date": f"2011-{month:02d}-01",
                "mode": "pipeline",
                "n_train": 24,
                "n_eval": 6,
                "n_days_in_month": 28,
                "rmse": 400 + i * 50,
                "mae": 300 + i * 40,
            }
        )
    for i, month in enumerate(range(2, 4)):
        rows.append(
            {
                "ref_date": f"2011-{month:02d}-01",
                "mode": "walk_forward",
                "n_train": 31 * month,
                "n_eval": 28,
                "n_days_in_month": 28,
                "rmse": 500 + i * 60,
                "mae": 400 + i * 30,
            }
        )
    return pd.DataFrame(rows)


def test_plot_and_xlsx_outputs(tmp_path: Path):
    csv_path = tmp_path / "report.csv"
    _sample_report().to_csv(csv_path, index=False)

    df = load_report(csv_path)
    png_path = tmp_path / "out.png"
    xlsx_path = tmp_path / "out.xlsx"

    plot_png(df, png_path)
    write_xlsx(df, xlsx_path)

    assert png_path.is_file() and png_path.stat().st_size > 0
    assert xlsx_path.is_file() and xlsx_path.stat().st_size > 0
