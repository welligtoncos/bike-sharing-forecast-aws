"""
Simula evolução do modelo mês a mês usando o day.csv completo (local ou S3).

Modos
-----
  pipeline      — Igual à esteira AWS: treina só com o mês de ref_date (split 80/20).
  walk_forward  — Treina com todo histórico anterior ao mês; avalia no mês inteiro
                  (out-of-sample, mostra evolução conforme o histórico cresce).

Uso
---
  python scripts/simulate_monthly_evolution.py --input-path s3://BUCKET/raw/day.csv
  python scripts/simulate_monthly_evolution.py --input-path data/day.csv --mode both
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Iterator, Literal

import pandas as pd

from schema_validation import (
    DATE_COLUMN,
    filter_by_ref_date,
    load_and_validate_day_csv,
    select_feature_columns,
    validate_schema,
)
from xgboost_training import (
    RANDOM_STATE,
    build_xgboost_regressor,
    compute_regression_metrics,
    split_features_target,
    split_train_validation,
)

logger = logging.getLogger(__name__)

SimulationMode = Literal["pipeline", "walk_forward"]


def load_day_csv(input_path: str) -> pd.DataFrame:
    """Carrega day.csv de s3:// ou caminho local."""
    if input_path.startswith("s3://"):
        return load_and_validate_day_csv(input_path)

    path = Path(input_path)
    if not path.is_file():
        raise FileNotFoundError(f"Arquivo nao encontrado: {input_path}")

    df = pd.read_csv(path)
    validate_schema(df)
    logger.info("DataFrame shape: %s", df.shape)
    return df


def iter_ref_dates_in_dataset(df: pd.DataFrame) -> Iterator[str]:
    """Gera ref_date (YYYY-MM-01) para cada mês presente no intervalo do dataset."""
    dates = pd.to_datetime(df[DATE_COLUMN])
    start = dates.min().replace(day=1)
    end = dates.max().replace(day=1)
    current = start
    while current <= end:
        yield f"{current.year}-{current.month:02d}-01"
        current = current + pd.offsets.MonthBegin(1)


def _month_start(ref_date: str) -> pd.Timestamp:
    parsed = pd.to_datetime(ref_date)
    return parsed.replace(day=1)


def features_for_month(df: pd.DataFrame, ref_date: str) -> pd.DataFrame | None:
    """Filtra mês e seleciona colunas de modelagem (equivalente S2)."""
    filtered = filter_by_ref_date(df, ref_date)
    if filtered.empty:
        return None
    return select_feature_columns(filtered)


def train_rows_before_month(df: pd.DataFrame, ref_date: str) -> pd.DataFrame | None:
    """Registros estritamente anteriores ao mês de ref_date."""
    start = _month_start(ref_date)
    dates = pd.to_datetime(df[DATE_COLUMN])
    subset = df.loc[dates < start]
    if subset.empty:
        return None
    return select_feature_columns(subset)


def evaluate_pipeline_month(
    df: pd.DataFrame,
    ref_date: str,
    *,
    random_state: int = RANDOM_STATE,
) -> dict[str, Any] | None:
    """Replica S3-01: treino/validação 80/20 só com dados do mês."""
    features_df = features_for_month(df, ref_date)
    if features_df is None:
        return None

    x, y = split_features_target(features_df)
    if len(x) < 2:
        return None

    x_train, x_val, y_train, y_val = split_train_validation(
        x,
        y,
        random_state=random_state,
    )
    model = build_xgboost_regressor(random_state=random_state)
    model.fit(x_train, y_train)
    metrics = compute_regression_metrics(y_val, model.predict(x_val))

    return {
        "ref_date": ref_date,
        "mode": "pipeline",
        "n_train": len(x_train),
        "n_eval": len(x_val),
        "n_days_in_month": len(x),
        **metrics,
    }


def evaluate_walk_forward_month(
    df: pd.DataFrame,
    ref_date: str,
    *,
    random_state: int = RANDOM_STATE,
) -> dict[str, Any] | None:
    """Treina com histórico acumulado; avalia no mês ref_date (sem vazamento)."""
    train_df = train_rows_before_month(df, ref_date)
    test_df = features_for_month(df, ref_date)
    if train_df is None or test_df is None:
        return None

    x_train, y_train = split_features_target(train_df)
    x_test, y_test = split_features_target(test_df)
    if len(x_train) < 2 or len(x_test) < 1:
        return None

    model = build_xgboost_regressor(random_state=random_state)
    model.fit(x_train, y_train)
    metrics = compute_regression_metrics(y_test, model.predict(x_test))

    return {
        "ref_date": ref_date,
        "mode": "walk_forward",
        "n_train": len(x_train),
        "n_eval": len(x_test),
        "n_days_in_month": len(x_test),
        **metrics,
    }


def run_simulation(
    df: pd.DataFrame,
    modes: list[SimulationMode],
    *,
    random_state: int = RANDOM_STATE,
) -> pd.DataFrame:
    """Executa simulação para todos os meses do dataset."""
    rows: list[dict[str, Any]] = []

    for ref_date in iter_ref_dates_in_dataset(df):
        if "pipeline" in modes:
            result = evaluate_pipeline_month(df, ref_date, random_state=random_state)
            if result is not None:
                rows.append(result)

        if "walk_forward" in modes:
            result = evaluate_walk_forward_month(df, ref_date, random_state=random_state)
            if result is not None:
                rows.append(result)

    if not rows:
        raise ValueError("Nenhum mes gerou metricas; verifique o dataset.")

    report = pd.DataFrame(rows)
    column_order = [
        "ref_date",
        "mode",
        "n_train",
        "n_eval",
        "n_days_in_month",
        "rmse",
        "mae",
    ]
    return report.loc[:, column_order].sort_values(["mode", "ref_date"]).reset_index(drop=True)


def print_summary(report: pd.DataFrame) -> None:
    """Imprime tabela legível no stdout."""
    print("\n=== Evolucao mensal do modelo ===\n")
    for mode in report["mode"].unique():
        subset = report.loc[report["mode"] == mode]
        print(f"--- Modo: {mode} ({len(subset)} meses) ---")
        print(
            subset.to_string(
                index=False,
                formatters={"rmse": "{:.2f}".format, "mae": "{:.2f}".format},
            )
        )
        print(
            f"Media RMSE={subset['rmse'].mean():.2f}  "
            f"Media MAE={subset['mae'].mean():.2f}\n"
        )


def parse_modes(value: str) -> list[SimulationMode]:
    normalized = value.strip().lower()
    if normalized == "both":
        return ["pipeline", "walk_forward"]
    if normalized in ("pipeline", "walk_forward"):
        return [normalized]  # type: ignore[list-item]
    raise argparse.ArgumentTypeError(
        "Modo invalido; use pipeline, walk_forward ou both."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Simula evolucao RMSE/MAE mes a mes com day.csv completo.",
    )
    parser.add_argument(
        "--input-path",
        required=True,
        help="s3://bucket/raw/day.csv ou caminho local para day.csv",
    )
    parser.add_argument(
        "--mode",
        type=parse_modes,
        default="both",
        help="pipeline (esteira AWS), walk_forward (historico acumulado) ou both",
    )
    parser.add_argument(
        "--output",
        default="evolution_report.csv",
        help="CSV de saida (default: evolution_report.csv)",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=RANDOM_STATE,
        help=f"Seed do XGBoost e split (default: {RANDOM_STATE})",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s %(name)s: %(message)s",
    )

    df = load_day_csv(args.input_path)
    report = run_simulation(df, args.mode, random_state=args.random_state)

    output_path = Path(args.output)
    report.to_csv(output_path, index=False)
    logger.info("Relatorio salvo em %s", output_path.resolve())

    print_summary(report)
    print(f"Relatorio CSV: {output_path.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
