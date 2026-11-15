"""Describe personal-baseline data availability in prepared NASA data.

The script deliberately does not calculate a baseline, choose a minimum sample
threshold, derive anomaly scores, train a model, or alter source measurements.
It only summarizes each astronaut and measurement history.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


INPUT_COLUMNS = {
    "ASTRONAUT_ID",
    "SOURCE_DATASET",
    "PANEL",
    "ORIGINAL_ANALYTE",
    "MEASUREMENT",
    "UNIT",
    "ORIGINAL_TIMEPOINT",
    "PHASE",
    "RELATIVE_DAY",
}

OUTPUT_COLUMNS = [
    "ASTRONAUT_ID",
    "SOURCE_DATASET",
    "PANEL",
    "ORIGINAL_ANALYTE",
    "MEASUREMENT",
    "UNIT",
    "TOTAL_OBSERVATION_COUNT",
    "PRE_FLIGHT_OBSERVATION_COUNT",
    "POST_FLIGHT_OBSERVATION_COUNT",
    "RELATIVE_DAYS_SORTED",
    "TIMEPOINTS_SORTED",
    "DATA_AVAILABILITY_NOTE",
]


def validate_input(data: pd.DataFrame) -> None:
    """Ensure the assessment is based on the approved prepared-data schema."""
    missing = INPUT_COLUMNS.difference(data.columns)
    if missing:
        raise ValueError(f"Input data is missing required columns: {sorted(missing)}")


def availability_note(pre_flight_count: int) -> str:
    """Describe available history without declaring a baseline-ready threshold."""
    if pre_flight_count == 0:
        return "no_pre_flight_history; personal baseline cannot be assessed from this series"
    if pre_flight_count == 1:
        return "one_pre_flight_observation; sparse personal history"
    if pre_flight_count == 2:
        return "two_pre_flight_observations; sparse personal history"
    return f"{pre_flight_count}_pre_flight_observations; sparse history, protocol decision still required"


def assess_measurement_histories(data: pd.DataFrame) -> pd.DataFrame:
    """Summarize each astronaut's own chronological measurement history."""
    working = data.copy()
    working["RELATIVE_DAY_NUMERIC"] = pd.to_numeric(working["RELATIVE_DAY"], errors="raise")

    group_columns = [
        "ASTRONAUT_ID",
        "SOURCE_DATASET",
        "PANEL",
        "ORIGINAL_ANALYTE",
        "MEASUREMENT",
        "UNIT",
    ]
    summaries: list[dict[str, object]] = []

    for group_key, history in working.groupby(group_columns, sort=True, dropna=False):
        history = history.sort_values("RELATIVE_DAY_NUMERIC", kind="stable")
        pre_flight_count = int((history["PHASE"] == "PRE_FLIGHT").sum())
        post_flight_count = int((history["PHASE"] == "POST_FLIGHT").sum())
        summaries.append(
            {
                **dict(zip(group_columns, group_key, strict=True)),
                "TOTAL_OBSERVATION_COUNT": len(history),
                "PRE_FLIGHT_OBSERVATION_COUNT": pre_flight_count,
                "POST_FLIGHT_OBSERVATION_COUNT": post_flight_count,
                "RELATIVE_DAYS_SORTED": " | ".join(history["RELATIVE_DAY"].astype(str)),
                "TIMEPOINTS_SORTED": " | ".join(history["ORIGINAL_TIMEPOINT"].astype(str)),
                "DATA_AVAILABILITY_NOTE": availability_note(pre_flight_count),
            }
        )

    return pd.DataFrame(summaries, columns=OUTPUT_COLUMNS)


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    input_path = project_root / "data" / "processed" / "nasa_long_measurements.csv"
    output_path = project_root / "data" / "processed" / "nasa_baseline_readiness_summary.csv"

    data = pd.read_csv(input_path, dtype=str, keep_default_na=False)
    validate_input(data)
    summary = assess_measurement_histories(data)
    summary.to_csv(output_path, index=False, encoding="utf-8")

    print(f"Measurement histories: {len(summary)}")
    print(f"Histories with three pre-flight observations: {(summary['PRE_FLIGHT_OBSERVATION_COUNT'] == 3).sum()}")
    print(f"Histories with two pre-flight observations: {(summary['PRE_FLIGHT_OBSERVATION_COUNT'] == 2).sum()}")
    print(f"Histories with no pre-flight observations: {(summary['PRE_FLIGHT_OBSERVATION_COUNT'] == 0).sum()}")


if __name__ == "__main__":
    main()
