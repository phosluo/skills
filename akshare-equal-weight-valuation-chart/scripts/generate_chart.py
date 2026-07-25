from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
from typing import Iterable, Sequence


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate monthly equal-weight PE/PB charts for All A Shares from AKShare."
    )
    parser.add_argument(
        "--start-date",
        default="2005-01-01",
        help="Inclusive start date in YYYY-MM-DD format. Default: 2005-01-01",
    )
    parser.add_argument(
        "--output",
        default="all_a_equal_weight_pe_pb_since_2005_monthly.png",
        help="Output PNG filename written to the current working directory.",
    )
    return parser.parse_args()


def month_index(value: date) -> int:
    return value.year * 12 + (value.month - 1)


def sample_every_month(
    points: Iterable[tuple[date, float]], start_date: date
) -> list[tuple[date, float]]:
    sampled: list[tuple[date, float]] = []
    current_bucket = None
    last_point: tuple[date, float] | None = None
    start_bucket = month_index(start_date)

    for point_date, point_value in sorted(points, key=lambda item: item[0]):
        bucket = month_index(point_date)
        if bucket < start_bucket:
            continue
        if current_bucket is None:
            current_bucket = bucket
        if bucket != current_bucket:
            if last_point is not None:
                sampled.append(last_point)
            current_bucket = bucket
        last_point = (point_date, point_value)

    if last_point is not None:
        sampled.append(last_point)

    return sampled


def pick_value_column(columns: Sequence[str], aliases: Sequence[str]) -> str | None:
    lowered = {str(column).lower(): str(column) for column in columns}
    for alias in aliases:
        if alias.lower() in lowered:
            return lowered[alias.lower()]
    return None


def load_equal_weight_series(dataset: str) -> list[tuple[date, float]]:
    try:
        import akshare as ak
        import pandas as pd
    except ModuleNotFoundError as exc:
        missing = exc.name or "dependency"
        raise SystemExit(
            f"Missing Python package: {missing}. "
            "Install with: python3 -m pip install --user akshare pandas matplotlib"
        ) from exc

    loaders = {
        "pe": (
            ak.stock_a_ttm_lyr,
            ("averagepettm", "average_pe_ttm", "average_pe"),
        ),
        "pb": (
            ak.stock_a_all_pb,
            ("equalweightaveragepb", "equal_weight_average_pb", "averagepb"),
        ),
    }
    if dataset not in loaders:
        raise SystemExit(f"Unsupported dataset: {dataset}")

    loader, aliases = loaders[dataset]
    df = loader()
    if df.empty:
        raise SystemExit(f"AKShare returned no data for dataset={dataset}")

    date_col = next(
        (col for col in df.columns if "日期" in str(col) or str(col).lower() == "date"),
        None,
    )
    value_col = pick_value_column([str(col) for col in df.columns], aliases)

    if date_col is None or value_col is None:
        raise SystemExit(f"Unexpected columns from AKShare {dataset}: {list(df.columns)}")

    frame = df[[date_col, value_col]].copy()
    frame[date_col] = pd.to_datetime(frame[date_col])
    frame[value_col] = pd.to_numeric(frame[value_col], errors="coerce")
    frame = frame.dropna().sort_values(date_col)

    return [
        (row[date_col].date(), float(row[value_col]))
        for _, row in frame.iterrows()
    ]


def plot_dual_series(
    pe_points: list[tuple[date, float]],
    pb_points: list[tuple[date, float]],
    output_path: Path,
) -> None:
    try:
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Missing Python package: matplotlib. "
            "Install with: python3 -m pip install --user matplotlib"
        ) from exc

    pe_dates = [point_date for point_date, _ in pe_points]
    pe_values = [point_value for _, point_value in pe_points]
    pb_dates = [point_date for point_date, _ in pb_points]
    pb_values = [point_value for _, point_value in pb_points]

    actual_start_date = min(pe_dates[0], pb_dates[0])
    actual_end_date = max(pe_dates[-1], pb_dates[-1])

    fig, axes = plt.subplots(2, 1, figsize=(14, 9), sharex=True)
    fig.suptitle(
        "All A Shares Equal-Weighted Valuation\n"
        f"({actual_start_date.isoformat()} to {actual_end_date.isoformat()}, Monthly Sampling)"
    )

    axes[0].plot(pe_dates, pe_values, linewidth=1.8, color="#1f5aa6")
    axes[0].set_ylabel("Equal-Weighted PE")
    axes[0].grid(True, linestyle="--", alpha=0.35)

    axes[1].plot(pb_dates, pb_values, linewidth=1.8, color="#c55a11")
    axes[1].set_ylabel("Equal-Weighted PB")
    axes[1].set_xlabel("Date")
    axes[1].grid(True, linestyle="--", alpha=0.35)

    year_locator = mdates.YearLocator()
    year_formatter = mdates.DateFormatter("%Y")
    axes[1].xaxis.set_major_locator(year_locator)
    axes[1].xaxis.set_major_formatter(year_formatter)
    fig.autofmt_xdate(rotation=45, ha="right")

    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    start_date = date.fromisoformat(args.start_date)
    output_path = Path.cwd() / args.output

    pe_points = sample_every_month(load_equal_weight_series("pe"), start_date=start_date)
    pb_points = sample_every_month(load_equal_weight_series("pb"), start_date=start_date)

    if not pe_points or not pb_points:
        raise SystemExit("No sampled points were generated.")

    plot_dual_series(pe_points, pb_points, output_path)

    first_date = min(pe_points[0][0], pb_points[0][0])
    last_date = max(pe_points[-1][0], pb_points[-1][0])

    print(f"Output: {output_path}")
    print(f"Requested start date: {start_date.isoformat()}")
    print(f"Actual data range: {first_date.isoformat()} to {last_date.isoformat()}")
    print("Sources: ak.stock_a_ttm_lyr() / ak.stock_a_all_pb()")


if __name__ == "__main__":
    main()
