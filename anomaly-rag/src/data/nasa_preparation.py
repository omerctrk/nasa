"""Prepare NASA OSD-569 and OSD-575 laboratory data for later analysis.

This module only normalizes source records and produces audit reports.  It does
not calculate a baseline, derive anomaly thresholds, train a model, or change
the source files.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Final
from zipfile import ZipFile

import pandas as pd


OUTPUT_COLUMNS: Final = [
    "ASTRONAUT_ID",
    "SOURCE_DATASET",
    "PANEL",
    "SAMPLE_NAME",
    "SPECIMEN_TYPE",
    "ORIGINAL_TIMEPOINT",
    "PHASE",
    "RELATIVE_DAY",
    "ORIGINAL_ANALYTE",
    "MEASUREMENT",
    "VALUE",
    "UNIT",
    "REFERENCE_LOW",
    "REFERENCE_HIGH",
    "DATA_QUALITY_NOTE",
]

QUALITY_COLUMNS: Final = [
    "SOURCE_DATASET",
    "PANEL",
    "ASTRONAUT_ID",
    "SAMPLE_NAME",
    "ORIGINAL_TIMEPOINT",
    "ORIGINAL_ANALYTE",
    "MEASUREMENT",
    "ISSUE_CODE",
    "SOURCE_FIELD",
    "SUBMITTED_VALUE",
    "TRANSFORMED_VALUE",
    "COMPARISON_STATUS",
    "NOTE",
]

CONSISTENCY_COLUMNS: Final = [
    "SOURCE_DATASET",
    "PANEL",
    "ASTRONAUT_ID",
    "SAMPLE_NAME",
    "ORIGINAL_TIMEPOINT",
    "ORIGINAL_ANALYTE",
    "MEASUREMENT",
    "CHECKED_FIELD",
    "TRANSFORMED_COLUMN",
    "SUBMITTED_VALUE",
    "TRANSFORMED_VALUE",
    "COMPARISON_STATUS",
    "NOTE",
]

CBC_MEASUREMENTS: Final = {
    "ABSOLUTE BASOPHILS": "absolute_basophils",
    "ABSOLUTE EOSINOPHILS": "absolute_eosinophils",
    "ABSOLUTE LYMPHOCYTES": "absolute_lymphocytes",
    "ABSOLUTE MONOCYTES": "absolute_monocytes",
    "ABSOLUTE NEUTROPHILS": "absolute_neutrophils",
    "BASOPHILS": "basophils_percent",
    "EOSINOPHILS": "eosinophils_percent",
    "HEMATOCRIT": "hematocrit_unqualified",
    "HEMATOCRIT (FEMALE)": "hematocrit_female_labeled",
    "HEMOGLOBIN": "hemoglobin_unqualified",
    "HEMOGLOBIN (FEMALE)": "hemoglobin_female_labeled",
    "LYMPHOCYTES": "lymphocytes_percent",
    "MCH": "mean_corpuscular_hemoglobin",
    "MCHC": "mean_corpuscular_hemoglobin_concentration",
    "MCV": "mean_corpuscular_volume",
    "MONOCYTES": "monocytes_percent",
    "MPV": "mean_platelet_volume",
    "NEUTROPHILS": "neutrophils_percent",
    "PLATELET COUNT": "platelet_count",
    "RDW": "red_cell_distribution_width",
    "RED BLOOD CELL COUNT": "red_blood_cell_count_unqualified",
    "RED BLOOD CELL COUNT (FEMALE)": "red_blood_cell_count_female_labeled",
    "WHITE BLOOD CELL COUNT": "white_blood_cell_count",
}

CMP_MEASUREMENTS: Final = {
    "ALBUMIN": "albumin",
    "ALBUMIN/GLOBULIN RATIO": "albumin_globulin_ratio",
    "ALKALINE PHOSPHATASE": "alkaline_phosphatase",
    "ALT": "alanine_aminotransferase",
    "AST": "aspartate_aminotransferase",
    "BILIRUBIN; TOTAL": "total_bilirubin",
    "BUN/CREATININE RATIO": "bun_creatinine_ratio",
    "CALCIUM": "calcium",
    "CARBON DIOXIDE": "carbon_dioxide",
    "CHLORIDE": "chloride",
    "CREATININE": "creatinine",
    "eGFR AFRICAN AMERICAN": "egfr_african_american",
    "eGFR NON-AFR. AMERICAN": "egfr_non_african_american",
    "GLOBULIN": "globulin",
    "GLUCOSE": "glucose",
    "POTASSIUM": "potassium",
    "PROTEIN; TOTAL": "total_protein",
    "SODIUM": "sodium",
    "UREA NITROGEN (BUN)": "urea_nitrogen_bun",
}


def transformed_columns(prefix: str) -> dict[str, str]:
    """Return the three transformed columns for a direct comparison."""
    return {
        "VALUE": f"{prefix}_value",
        "RANGE_MIN": f"{prefix}_range_min",
        "RANGE_MAX": f"{prefix}_range_max",
    }


# Exact transformed names are kept here so the audit never guesses a column.
DIRECT_TRANSFORMED: Final = {
    "ABSOLUTE BASOPHILS": {
        "VALUE": "absolute_basophils_value_cells_per_microliter",
        "RANGE_MIN": "absolute_basophils_range_min_cells_per_microliter",
        "RANGE_MAX": "absolute_basophils_range_max_cells_per_microliter",
    },
    "ABSOLUTE EOSINOPHILS": {
        "VALUE": "absolute_eosinophils_value_cells_per_microliter",
        "RANGE_MIN": "absolute_eosinophils_range_min_cells_per_microliter",
        "RANGE_MAX": "absolute_eosinophils_range_max_cells_per_microliter",
    },
    "ABSOLUTE LYMPHOCYTES": {
        "VALUE": "absolute_lymphocytes_value_cells_per_microliter",
        "RANGE_MIN": "absolute_lymphocytes_range_min_cells_per_microliter",
        "RANGE_MAX": "absolute_lymphocytes_range_max_cells_per_microliter",
    },
    "ABSOLUTE MONOCYTES": {
        "VALUE": "absolute_monocytes_value_cells_per_microliter",
        "RANGE_MIN": "absolute_monocytes_range_min_cells_per_microliter",
        "RANGE_MAX": "absolute_monocytes_range_max_cells_per_microliter",
    },
    "ABSOLUTE NEUTROPHILS": {
        "VALUE": "absolute_neutrophils_value_cells_per_microliter",
        "RANGE_MIN": "absolute_neutrophils_range_min_cells_per_microliter",
        "RANGE_MAX": "absolute_neutrophils_range_max_cells_per_microliter",
    },
    "BASOPHILS": {
        "VALUE": "basophils_value_percent",
        "RANGE_MIN": "basophils_range_min_percent",
        "RANGE_MAX": "basophils_range_max_percent",
    },
    "EOSINOPHILS": {
        "VALUE": "eosinophils_value_percent",
        "RANGE_MIN": "eosinophils_range_min_percent",
        "RANGE_MAX": "eosinophils_range_max_percent",
    },
    "HEMATOCRIT": {
        "VALUE": "hematocrit_value_percent",
        "RANGE_MIN": "hematocrit_range_min_percent",
        "RANGE_MAX": "hematocrit_range_max_percent",
    },
    "LYMPHOCYTES": {
        "VALUE": "lymphocytes_value_percent",
        "RANGE_MIN": "lymphocytes_range_min_percent",
        "RANGE_MAX": "lymphocytes_range_max_percent",
    },
    "MCH": {
        "VALUE": "mch_value_picogram",
        "RANGE_MIN": "mch_range_min_picogram",
        "RANGE_MAX": "mch_range_max_picogram",
    },
    "MCHC": {
        "VALUE": "mchc_value_grams_per_deciliter",
        "RANGE_MIN": "mchc_range_min_grams_per_deciliter",
        "RANGE_MAX": "mchc_range_max_grams_per_deciliter",
    },
    "MCV": {
        "VALUE": "mcv_value_femtoliter",
        "RANGE_MIN": "mcv_range_min_femtoliter",
        "RANGE_MAX": "mcv_range_max_femtoliter",
    },
    "MONOCYTES": {
        "VALUE": "monocytes_value_percent",
        "RANGE_MIN": "monocytes_range_min_percent",
        "RANGE_MAX": "monocytes_range_max_percent",
    },
    "MPV": {
        "VALUE": "mpv_value_femtoliter",
        "RANGE_MIN": "mpv_range_min_femtoliter",
        "RANGE_MAX": "mpv_range_max_femtoliter",
    },
    "NEUTROPHILS": {
        "VALUE": "neutrophils_value_percent",
        "RANGE_MIN": "neutrophils_range_min_percent",
        "RANGE_MAX": "neutrophils_range_max_percent",
    },
    "PLATELET COUNT": {
        "VALUE": "platelet_count_value_thousand_per_microliter",
        "RANGE_MIN": "platelet_count_range_min_thousand_per_microliter",
        "RANGE_MAX": "platelet_count_range_max_thousand_per_microliter",
    },
    "RDW": {
        "VALUE": "rdw_value_percent",
        "RANGE_MIN": "rdw_range_min_percent",
        "RANGE_MAX": "rdw_range_max_percent",
    },
    "RED BLOOD CELL COUNT": {
        "VALUE": "red_blood_cell_count_value_million_per_microliter",
        "RANGE_MIN": "red_blood_cell_count_range_min_million_per_microliter",
        "RANGE_MAX": "red_blood_cell_count_range_max_million_per_microliter",
    },
    "WHITE BLOOD CELL COUNT": {
        "VALUE": "white_blood_cell_count_value_thousand_per_microliter",
        "RANGE_MIN": "white_blood_cell_count_range_min_thousand_per_microliter",
        "RANGE_MAX": "white_blood_cell_count_range_max_thousand_per_microliter",
    },
    "ALBUMIN": {
        "VALUE": "albumin_value_gram_per_deciliter",
        "RANGE_MIN": "albumin_range_min_gram_per_deciliter",
        "RANGE_MAX": "albumin_range_max_gram_per_deciliter",
    },
    "ALKALINE PHOSPHATASE": {
        "VALUE": "alkaline_phosphatase_value_units_per_liter",
        "RANGE_MIN": "alkaline_phosphatase_range_min_units_per_liter",
        "RANGE_MAX": "alkaline_phosphatase_range_max_units_per_liter",
    },
    "BILIRUBIN; TOTAL": {
        "VALUE": "total_bilirubin_value_milligram_per_deciliter",
        "RANGE_MIN": "total_bilirubin_range_min_milligram_per_deciliter",
        "RANGE_MAX": "total_bilirubin_range_max_milligram_per_deciliter",
    },
    "CALCIUM": {
        "VALUE": "calcium_value_milligram_per_deciliter",
        "RANGE_MIN": "calcium_range_min_milligram_per_deciliter",
        "RANGE_MAX": "calcium_range_max_milligram_per_deciliter",
    },
    "CARBON DIOXIDE": {
        "VALUE": "carbon_dioxide_value_millimol_per_liter",
        "RANGE_MIN": "carbon_dioxide_range_min_millimol_per_liter",
        "RANGE_MAX": "carbon_dioxide_range_max_millimol_per_liter",
    },
    "CHLORIDE": {
        "VALUE": "chloride_value_millimol_per_liter",
        "RANGE_MIN": "chloride_range_min_millimol_per_liter",
        "RANGE_MAX": "chloride_range_max_millimol_per_liter",
    },
    "CREATININE": {
        "VALUE": "creatinine_value_milligram_per_deciliter",
        "RANGE_MIN": "creatinine_range_min_milligram_per_deciliter",
        "RANGE_MAX": "creatinine_range_max_milligram_per_deciliter",
    },
    "eGFR AFRICAN AMERICAN": {
        "VALUE": "egfr_african_american_value_milliliter_per_minute_per_1.73_meter_squared",
        "RANGE_MIN": "egfr_african_american_range_min_milliliter_per_minute_per_1.73_meter_squared",
        "RANGE_MAX": "egfr_african_american_range_max_milliliter_per_minute_per_1.73_meter_squared",
    },
    "eGFR NON-AFR. AMERICAN": {
        "VALUE": "egfr_non_african_american_value_milliliter_per_minute_per_1.73_meter_squared",
        "RANGE_MIN": "egfr_non_african_american_range_min_milliliter_per_minute_per_1.73_meter_squared",
        "RANGE_MAX": "egfr_non_african_american_range_max_milliliter_per_minute_per_1.73_meter_squared",
    },
    "GLOBULIN": {
        "VALUE": "globulin_value_gram_per_deciliter",
        "RANGE_MIN": "globulin_range_min_gram_per_deciliter",
        "RANGE_MAX": "globulin_range_max_gram_per_deciliter",
    },
    "GLUCOSE": {
        "VALUE": "glucose_value_milligram_per_deciliter",
        "RANGE_MIN": "glucose_range_min_milligram_per_deciliter",
        "RANGE_MAX": "glucose_range_max_milligram_per_deciliter",
    },
    "POTASSIUM": {
        "VALUE": "potassium_value_millimol_per_liter",
        "RANGE_MIN": "potassium_range_min_millimol_per_liter",
        "RANGE_MAX": "potassium_range_max_millimol_per_liter",
    },
    "PROTEIN; TOTAL": {
        "VALUE": "total_protein_value_gram_per_deciliter",
        "RANGE_MIN": "total_protein_range_min_gram_per_deciliter",
        "RANGE_MAX": "total_protein_range_max_gram_per_deciliter",
    },
    "SODIUM": {
        "VALUE": "sodium_value_millimol_per_liter",
        "RANGE_MIN": "sodium_range_min_millimol_per_liter",
        "RANGE_MAX": "sodium_range_max_millimol_per_liter",
    },
    "UREA NITROGEN (BUN)": {
        "VALUE": "urea_nitrogen_bun_value_milligram_per_deciliter",
        "RANGE_MIN": "urea_nitrogen_bun_range_min_milligram_per_deciliter",
        "RANGE_MAX": "urea_nitrogen_bun_range_max_milligram_per_deciliter",
    },
}

REVIEW_TRANSFORMED: Final = {
    "HEMATOCRIT (FEMALE)": {
        "status": "REVIEW_REQUIRED",
        "columns": [
            "hematocrit_value_percent",
            "hematocrit_range_min_percent",
            "hematocrit_range_max_percent",
        ],
        "note": "No transformed column preserves the FEMALE source label.",
    },
    "HEMOGLOBIN": {
        "status": "UNMAPPED",
        "columns": [
            "hemoglobin_value_percent",
            "hemoglobin_range_min_percent",
            "hemoglobin_range_max_percent",
        ],
        "note": "Submitted unit is g/dL, while transformed headers state percent.",
    },
    "HEMOGLOBIN (FEMALE)": {
        "status": "UNMAPPED",
        "columns": [
            "hemoglobin_value_percent",
            "hemoglobin_range_min_percent",
            "hemoglobin_range_max_percent",
        ],
        "note": "Submitted unit is g/dL, transformed headers state percent, and the FEMALE label is absent.",
    },
    "RED BLOOD CELL COUNT (FEMALE)": {
        "status": "REVIEW_REQUIRED",
        "columns": [
            "red_blood_cell_count_value_million_per_microliter",
            "red_blood_cell_count_range_min_million_per_microliter",
            "red_blood_cell_count_range_max_million_per_microliter",
        ],
        "note": "No transformed column preserves the FEMALE source label.",
    },
    "ALBUMIN/GLOBULIN RATIO": {
        "status": "REVIEW_REQUIRED",
        "columns": [
            "albumin_to_globulin_ratio_value",
            "albumin_to_globulin_ratio_range_min",
            "albumin_to_globulin_ratio_range_max",
        ],
        "note": "The transformed name uses 'to' where the submitted source uses '/'.",
    },
    "BUN/CREATININE RATIO": {
        "status": "REVIEW_REQUIRED",
        "columns": [
            "bun_to_creatinine_ratio_value",
            "bun_to_creatinine_ratio_range_min",
            "bun_to_creatinine_ratio_range_max",
        ],
        "note": "The transformed name uses 'to' where the submitted source uses '/'.",
    },
    "ALT": {
        "status": "REVIEW_REQUIRED",
        "columns": [
            "alt_value_units_per_liter",
            "alt_range_min_units_per_liter",
            "alt_max_units_per_liter",
        ],
        "note": "The transformed upper-bound column does not use the range_max naming convention.",
    },
    "AST": {
        "status": "REVIEW_REQUIRED",
        "columns": [
            "ast_value_units_per_liter",
            "ast_range_min_units_per_liter",
            "ast_max_units_per_liter",
        ],
        "note": "The transformed upper-bound column does not use the range_max naming convention.",
    },
}

# Used only to detect an absent source record. It does not merge output rows.
COVERAGE_FAMILY: Final = {
    "HEMATOCRIT (FEMALE)": "HEMATOCRIT",
    "HEMOGLOBIN (FEMALE)": "HEMOGLOBIN",
    "RED BLOOD CELL COUNT (FEMALE)": "RED BLOOD CELL COUNT",
}


def read_csv_as_text(path: Path) -> pd.DataFrame:
    """Read CSV content without coercing values, units, or blank cells."""
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def read_metadata(zip_path: Path) -> pd.DataFrame:
    """Read the ISA sample table directly from its ZIP archive."""
    with ZipFile(zip_path) as archive:
        sample_table = next(name for name in archive.namelist() if name.startswith("s_"))
        with archive.open(sample_table) as handle:
            return pd.read_csv(handle, sep="\t", dtype=str, keep_default_na=False)


def parse_timepoint(label: str) -> tuple[str, str, str]:
    """Convert L-/R+ labels while deliberately avoiding a mission-day value."""
    if label.startswith("L-"):
        day = label.removeprefix("L-")
        return "PRE_FLIGHT", f"-{day}", f"Launch minus {day}"
    if label.startswith("R+"):
        day = label.removeprefix("R+")
        return "POST_FLIGHT", day, f"Return plus {day}"
    raise ValueError(f"Unsupported timepoint label: {label}")


def as_decimal(value: str) -> Decimal | None:
    """Parse numeric source strings only for comparison, never for output conversion."""
    if value == "":
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def values_match(submitted: str, transformed: str) -> bool:
    """Compare numeric strings without changing their source representation."""
    submitted_decimal = as_decimal(submitted)
    transformed_decimal = as_decimal(transformed)
    if submitted_decimal is not None and transformed_decimal is not None:
        return submitted_decimal == transformed_decimal
    return submitted == transformed


def quality_row(**values: str) -> dict[str, str]:
    """Create a quality-report row with a stable column set."""
    return {column: values.get(column, "") for column in QUALITY_COLUMNS}


def consistency_row(**values: str) -> dict[str, str]:
    """Create a transformed-consistency row with a stable column set."""
    return {column: values.get(column, "") for column in CONSISTENCY_COLUMNS}


def metadata_match(
    metadata: pd.DataFrame,
    astronaut_id: str,
    original_timepoint: str,
    specimen_type: str,
    expected_sample_name: str,
) -> pd.DataFrame:
    """Find the one metadata row that represents a submitted panel sample."""
    _, _, metadata_time = parse_timepoint(original_timepoint)
    return metadata.loc[
        (metadata["Source Name"] == astronaut_id)
        & (metadata["Factor Value[Time]"] == metadata_time)
        & (metadata["Characteristics[Material Type]"] == specimen_type)
        & (metadata["Sample Name"] == expected_sample_name)
    ]


def build_panel(
    *,
    submitted_path: Path,
    metadata_path: Path,
    source_dataset: str,
    panel: str,
    time_column: str,
    specimen_type: str,
    measurement_map: dict[str, str],
    sample_name_template: str,
) -> tuple[pd.DataFrame, list[dict[str, str]]]:
    """Create one long-format panel and source/metadata quality findings."""
    submitted = read_csv_as_text(submitted_path)
    metadata = read_metadata(metadata_path)
    output_rows: list[dict[str, str]] = []
    quality_rows: list[dict[str, str]] = []

    for source in submitted.to_dict(orient="records"):
        astronaut_id = source["SUBJECT_ID"]
        original_timepoint = source[time_column]
        phase, relative_day, _ = parse_timepoint(original_timepoint)
        expected_sample_name = sample_name_template.format(
            astronaut_id=astronaut_id,
            original_timepoint=original_timepoint,
        )
        matched_metadata = metadata_match(
            metadata,
            astronaut_id,
            original_timepoint,
            specimen_type,
            expected_sample_name,
        )

        quality_notes: list[str] = []
        if len(matched_metadata) == 1:
            metadata_record = matched_metadata.iloc[0]
            sample_name = metadata_record["Sample Name"]
            matched_specimen_type = metadata_record["Characteristics[Material Type]"]
        else:
            # A generated name is only a lookup candidate. It is not a verified
            # metadata value and must not be written into the output record.
            sample_name = ""
            matched_specimen_type = ""
            issue = "MISSING_METADATA" if len(matched_metadata) == 0 else "MULTIPLE_METADATA_MATCHES"
            quality_notes.append(issue.lower())
            quality_rows.append(
                quality_row(
                    SOURCE_DATASET=source_dataset,
                    PANEL=panel,
                    ASTRONAUT_ID=astronaut_id,
                    SAMPLE_NAME="",
                    ORIGINAL_TIMEPOINT=original_timepoint,
                    ORIGINAL_ANALYTE=source["ANALYTE"],
                    MEASUREMENT=measurement_map.get(source["ANALYTE"], ""),
                    ISSUE_CODE=issue,
                    SOURCE_FIELD="metadata",
                    COMPARISON_STATUS=issue,
                    NOTE=(
                        "Metadata matching must return exactly one row. "
                        f"Lookup candidate was {expected_sample_name}."
                    ),
                )
            )

        measurement = measurement_map.get(source["ANALYTE"], "")
        if measurement == "":
            quality_notes.append("unmapped_measurement")
            quality_rows.append(
                quality_row(
                    SOURCE_DATASET=source_dataset,
                    PANEL=panel,
                    ASTRONAUT_ID=astronaut_id,
                    SAMPLE_NAME=sample_name,
                    ORIGINAL_TIMEPOINT=original_timepoint,
                    ORIGINAL_ANALYTE=source["ANALYTE"],
                    ISSUE_CODE="UNMAPPED_MEASUREMENT",
                    SOURCE_FIELD="ANALYTE",
                    SUBMITTED_VALUE=source["ANALYTE"],
                    COMPARISON_STATUS="UNMAPPED",
                    NOTE="No approved standard measurement name exists.",
                )
            )

        for source_field in ("VALUE", "UNITS", "RANGE_MIN", "RANGE_MAX"):
            if source[source_field] == "":
                quality_notes.append(f"missing_{source_field.lower()}")
                quality_rows.append(
                    quality_row(
                        SOURCE_DATASET=source_dataset,
                        PANEL=panel,
                        ASTRONAUT_ID=astronaut_id,
                        SAMPLE_NAME=sample_name,
                        ORIGINAL_TIMEPOINT=original_timepoint,
                        ORIGINAL_ANALYTE=source["ANALYTE"],
                        MEASUREMENT=measurement,
                        ISSUE_CODE="MISSING_SOURCE_FIELD",
                        SOURCE_FIELD=source_field,
                        COMPARISON_STATUS="MISSING_IN_SUBMITTED",
                        NOTE="The raw submitted value is retained as blank; no imputation is applied.",
                    )
                )

        value = as_decimal(source["VALUE"])
        lower = as_decimal(source["RANGE_MIN"])
        upper = as_decimal(source["RANGE_MAX"])
        if value is not None and lower is not None and upper is not None and (value < lower or value > upper):
            quality_notes.append("outside_source_reference_interval; retained_unchanged")
            quality_rows.append(
                quality_row(
                    SOURCE_DATASET=source_dataset,
                    PANEL=panel,
                    ASTRONAUT_ID=astronaut_id,
                    SAMPLE_NAME=sample_name,
                    ORIGINAL_TIMEPOINT=original_timepoint,
                    ORIGINAL_ANALYTE=source["ANALYTE"],
                    MEASUREMENT=measurement,
                    ISSUE_CODE="OUTSIDE_SOURCE_REFERENCE_INTERVAL",
                    SOURCE_FIELD="VALUE",
                    SUBMITTED_VALUE=source["VALUE"],
                    COMPARISON_STATUS="REVIEW_REQUIRED",
                    NOTE="Source reference intervals are retained for quality review and are not anomaly thresholds.",
                )
            )

        output_rows.append(
            {
                "ASTRONAUT_ID": astronaut_id,
                "SOURCE_DATASET": source_dataset,
                "PANEL": panel,
                "SAMPLE_NAME": sample_name,
                "SPECIMEN_TYPE": matched_specimen_type,
                "ORIGINAL_TIMEPOINT": original_timepoint,
                "PHASE": phase,
                "RELATIVE_DAY": relative_day,
                "ORIGINAL_ANALYTE": source["ANALYTE"],
                "MEASUREMENT": measurement,
                "VALUE": source["VALUE"],
                "UNIT": source["UNITS"],
                "REFERENCE_LOW": source["RANGE_MIN"],
                "REFERENCE_HIGH": source["RANGE_MAX"],
                "DATA_QUALITY_NOTE": "; ".join(quality_notes),
            }
        )

    return pd.DataFrame(output_rows, columns=OUTPUT_COLUMNS), quality_rows


def expected_missing_records(panel_data: pd.DataFrame) -> list[dict[str, str]]:
    """Report missing source records without manufacturing rows in the output."""
    quality_rows: list[dict[str, str]] = []
    contexts = panel_data[["ASTRONAUT_ID", "ORIGINAL_TIMEPOINT"]].drop_duplicates()
    panel = panel_data.iloc[0]["PANEL"]
    source_dataset = panel_data.iloc[0]["SOURCE_DATASET"]

    coverage = panel_data.assign(
        COVERAGE_ANALYTE=panel_data["ORIGINAL_ANALYTE"].replace(COVERAGE_FAMILY)
    )
    for analyte in sorted(coverage["COVERAGE_ANALYTE"].unique()):
        observed = coverage.loc[coverage["COVERAGE_ANALYTE"] == analyte, ["ASTRONAUT_ID", "ORIGINAL_TIMEPOINT"]]
        observed_keys = set(map(tuple, observed.to_numpy()))
        for astronaut_id, timepoint in contexts.to_numpy():
            if (astronaut_id, timepoint) not in observed_keys:
                measurement = panel_data.loc[
                    panel_data["ORIGINAL_ANALYTE"] == analyte, "MEASUREMENT"
                ].iloc[0]
                quality_rows.append(
                    quality_row(
                        SOURCE_DATASET=source_dataset,
                        PANEL=panel,
                        ASTRONAUT_ID=astronaut_id,
                        ORIGINAL_TIMEPOINT=timepoint,
                        ORIGINAL_ANALYTE=analyte,
                        MEASUREMENT=measurement,
                        ISSUE_CODE="MISSING_MEASUREMENT_RECORD",
                        SOURCE_FIELD="source_row",
                        COMPARISON_STATUS="MISSING_IN_SUBMITTED",
                        NOTE="No source row exists; no output measurement is created.",
                    )
                )
    return quality_rows


def transformed_consistency(
    panel_data: pd.DataFrame,
    transformed_path: Path,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Audit transformed values without allowing them to alter output values."""
    transformed = read_csv_as_text(transformed_path).set_index("Sample Name", drop=False)
    consistency_rows: list[dict[str, str]] = []
    quality_rows: list[dict[str, str]] = []

    for row in panel_data.to_dict(orient="records"):
        common = {
            "SOURCE_DATASET": row["SOURCE_DATASET"],
            "PANEL": row["PANEL"],
            "ASTRONAUT_ID": row["ASTRONAUT_ID"],
            "SAMPLE_NAME": row["SAMPLE_NAME"],
            "ORIGINAL_TIMEPOINT": row["ORIGINAL_TIMEPOINT"],
            "ORIGINAL_ANALYTE": row["ORIGINAL_ANALYTE"],
            "MEASUREMENT": row["MEASUREMENT"],
        }
        analyte = row["ORIGINAL_ANALYTE"]
        if analyte in REVIEW_TRANSFORMED:
            review = REVIEW_TRANSFORMED[analyte]
            consistency_rows.append(
                consistency_row(
                    **common,
                    CHECKED_FIELD="ALL",
                    TRANSFORMED_COLUMN=" | ".join(review["columns"]),
                    COMPARISON_STATUS=review["status"],
                    NOTE=review["note"],
                )
            )
            quality_rows.append(
                quality_row(
                    **common,
                    ISSUE_CODE=f"TRANSFORMED_{review['status']}",
                    SOURCE_FIELD="transformed_mapping",
                    COMPARISON_STATUS=review["status"],
                    NOTE=review["note"],
                )
            )
            continue

        if row["SAMPLE_NAME"] not in transformed.index:
            consistency_rows.append(
                consistency_row(
                    **common,
                    CHECKED_FIELD="ALL",
                    COMPARISON_STATUS="MISSING_TRANSFORMED_SAMPLE",
                    NOTE="No matching transformed sample was found.",
                )
            )
            quality_rows.append(
                quality_row(
                    **common,
                    ISSUE_CODE="MISSING_TRANSFORMED_SAMPLE",
                    SOURCE_FIELD="Sample Name",
                    COMPARISON_STATUS="MISSING_TRANSFORMED_SAMPLE",
                    NOTE="The transformed file is an audit source only.",
                )
            )
            continue

        mapping = DIRECT_TRANSFORMED[analyte]
        transformed_record = transformed.loc[row["SAMPLE_NAME"]]
        for source_field, transformed_column in mapping.items():
            source_value = row[{"VALUE": "VALUE", "RANGE_MIN": "REFERENCE_LOW", "RANGE_MAX": "REFERENCE_HIGH"}[source_field]]
            transformed_value = transformed_record[transformed_column]
            status = "MATCH" if values_match(source_value, transformed_value) else "MISMATCH"
            note = "Exact numeric/text comparison." if status == "MATCH" else "Submitted value remains authoritative."
            consistency_rows.append(
                consistency_row(
                    **common,
                    CHECKED_FIELD=source_field,
                    TRANSFORMED_COLUMN=transformed_column,
                    SUBMITTED_VALUE=source_value,
                    TRANSFORMED_VALUE=transformed_value,
                    COMPARISON_STATUS=status,
                    NOTE=note,
                )
            )
            if status == "MISMATCH":
                quality_rows.append(
                    quality_row(
                        **common,
                        ISSUE_CODE="TRANSFORMED_VALUE_MISMATCH",
                        SOURCE_FIELD=source_field,
                        SUBMITTED_VALUE=source_value,
                        TRANSFORMED_VALUE=transformed_value,
                        COMPARISON_STATUS=status,
                        NOTE=f"Compared against transformed column {transformed_column}; submitted value is retained.",
                    )
                )
    return consistency_rows, quality_rows


def write_csv(frame: pd.DataFrame, path: Path, columns: list[str]) -> None:
    """Write CSV with explicit column order and no index."""
    frame.reindex(columns=columns).to_csv(path, index=False, encoding="utf-8")


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    raw_root = project_root / "data" / "raw"
    output_root = project_root / "data" / "processed"
    output_root.mkdir(parents=True, exist_ok=True)

    cbc_data, cbc_quality = build_panel(
        submitted_path=raw_root / "OSD-569" / "LSDS-7_Complete_Blood_Count_CBC.upload_SUBMITTED.csv",
        metadata_path=raw_root / "OSD-569" / "OSD-569_metadata_OSD-569-ISA.zip",
        source_dataset="OSD-569",
        panel="CBC",
        time_column="TEST_DATE",
        specimen_type="Whole Blood",
        measurement_map=CBC_MEASUREMENTS,
        sample_name_template="{astronaut_id}_whole-blood_{original_timepoint}_cbc",
    )
    cmp_data, cmp_quality = build_panel(
        submitted_path=raw_root / "OSD-575" / "LSDS-8_Comprehensive_Metabolic_Panel_CMP.upload_SUBMITTED.csv",
        metadata_path=raw_root / "OSD-575" / "OSD-575_metadata_OSD-575-ISA.zip",
        source_dataset="OSD-575",
        panel="CMP",
        time_column="timepoint",
        specimen_type="Serum",
        measurement_map=CMP_MEASUREMENTS,
        sample_name_template="{astronaut_id}_serum_{original_timepoint}",
    )

    quality_rows = cbc_quality + cmp_quality
    quality_rows += expected_missing_records(cbc_data)
    quality_rows += expected_missing_records(cmp_data)

    cbc_consistency, cbc_consistency_quality = transformed_consistency(
        cbc_data,
        raw_root / "OSD-569" / "LSDS-7_Complete_Blood_Count_CBC_TRANSFORMED.csv",
    )
    cmp_consistency, cmp_consistency_quality = transformed_consistency(
        cmp_data,
        raw_root / "OSD-575" / "LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv",
    )
    quality_rows += cbc_consistency_quality + cmp_consistency_quality

    combined = pd.concat([cbc_data, cmp_data], ignore_index=True)
    quality_frame = pd.DataFrame(quality_rows, columns=QUALITY_COLUMNS)
    consistency_frame = pd.DataFrame(cbc_consistency + cmp_consistency, columns=CONSISTENCY_COLUMNS)

    write_csv(cbc_data, output_root / "nasa_cbc_long_measurements.csv", OUTPUT_COLUMNS)
    write_csv(cmp_data, output_root / "nasa_cmp_long_measurements.csv", OUTPUT_COLUMNS)
    write_csv(combined, output_root / "nasa_long_measurements.csv", OUTPUT_COLUMNS)
    write_csv(quality_frame, output_root / "nasa_data_quality_report.csv", QUALITY_COLUMNS)
    write_csv(consistency_frame, output_root / "nasa_transformed_consistency_report.csv", CONSISTENCY_COLUMNS)

    if list(combined.columns) != OUTPUT_COLUMNS:
        raise RuntimeError("The combined output does not match the approved 15-column schema.")
    if len(combined) != len(cbc_data) + len(cmp_data):
        raise RuntimeError("The combined output row count is inconsistent with panel outputs.")

    print(f"CBC rows: {len(cbc_data)}")
    print(f"CMP rows: {len(cmp_data)}")
    print(f"Combined rows: {len(combined)}")
    print(f"Quality findings: {len(quality_frame)}")
    print(f"Consistency checks: {len(consistency_frame)}")


if __name__ == "__main__":
    main()
