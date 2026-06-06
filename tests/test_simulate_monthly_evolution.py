"""
Testes — simulacao de evolucao mensal (dataset completo local).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from simulate_monthly_evolution import (  # noqa: E402
    evaluate_pipeline_month,
    evaluate_walk_forward_month,
    iter_ref_dates_in_dataset,
    run_simulation,
)

pytest.importorskip("xgboost")


def _synthetic_day_csv(months: int = 4, days_per_month: int = 5) -> pd.DataFrame:
    rows = []
    for month in range(1, months + 1):
        for day in range(1, days_per_month + 1):
            rows.append(
                {
                    "dteday": f"2011-{month:02d}-{day:02d}",
                    "season": 1,
                    "temp": 0.4 + day * 0.01,
                    "hum": 0.5,
                    "windspeed": 0.2,
                    "weekday": day % 7,
                    "cnt": 100 + month * 10 + day,
                }
            )
    return pd.DataFrame(rows)


def test_iter_ref_dates_in_dataset():
    df = _synthetic_day_csv(months=3)
    dates = list(iter_ref_dates_in_dataset(df))
    assert dates == ["2011-01-01", "2011-02-01", "2011-03-01"]


def test_pipeline_month_returns_metrics():
    df = _synthetic_day_csv(months=1, days_per_month=10)
    result = evaluate_pipeline_month(df, "2011-01-01")
    assert result is not None
    assert result["mode"] == "pipeline"
    assert result["rmse"] >= 0
    assert result["mae"] >= 0
    assert result["n_train"] + result["n_eval"] == 10


def test_walk_forward_skips_first_month_without_history():
    df = _synthetic_day_csv(months=3, days_per_month=8)
    assert evaluate_walk_forward_month(df, "2011-01-01") is None
    result = evaluate_walk_forward_month(df, "2011-02-01")
    assert result is not None
    assert result["n_train"] == 8
    assert result["n_eval"] == 8


def test_run_simulation_both_modes():
    df = _synthetic_day_csv(months=4, days_per_month=10)
    report = run_simulation(df, ["pipeline", "walk_forward"])
    assert len(report) == 4 + 3  # pipeline: 4 meses; walk_forward: 3 (sem jan)
    assert set(report["mode"]) == {"pipeline", "walk_forward"}
    assert report["rmse"].notna().all()
