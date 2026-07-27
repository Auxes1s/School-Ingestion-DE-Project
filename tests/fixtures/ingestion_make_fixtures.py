"""Regenerate the committed ingestion fixtures under ``tests/fixtures/ingestion_raw/``.

Run with ``uv run python tests/fixtures/ingestion_make_fixtures.py``.

These files stand in for the slice-2 generator's output so ingestion can be built and
tested without it. Every header is drawn from ``configs/schema_registry.yml`` alias
lists, and each file carries at least one deliberate defect the ingester must handle
rather than crash on:

============================================  ==========================================
File                                          What it exercises
============================================  ==========================================
``baseline/SCH_0001_baseline.xlsx``           title row above the header, a non-default
                                              sheet name, an unmapped ``Remarks``
                                              column, and every date format
``baseline/SCH_0002_baseline.csv``            missing required ``sex``, missing optional
                                              columns, CSV path
``baseline/SCH_0003_baseline.csv``            missing ``minimum_viable`` columns — this
                                              file must fail, not be silently dropped
``endline/SCH_0001_endline.xlsx``             the same school at endline
``enrollment/enrollment_sy2024_2025.csv``     ``enrollment_snapshot``
``allocation/allocation_sy2024_2025.csv``     ``program_allocation``
``reference/school_masterlist.xlsx``          ``school_masterlist`` with treatment values
                                              needing ``value_normalization``
============================================  ==========================================
"""

from __future__ import annotations

import csv
from pathlib import Path

from openpyxl import Workbook

FIXTURE_ROOT = Path(__file__).parent / "ingestion_raw"

#: One child per row, spanning every date format the parser claims to support and every
#: sex spelling in ``value_normalization``.
BASELINE_ROWS: list[list[object]] = [
    [
        "Bagumbayan ES",
        "SCH_0001",
        "136420010001",
        "SANTOS, MARIA C.",
        "02/17/2019",
        "M",
        "Grade 1",
        "108.4",
        "18.2",
        "2024-08-15",
        "none",
    ],
    [
        "Bagumbayan ES",
        "SCH_0001",
        "136420010002",
        "REYES, JUAN P.",
        "01/02/2019",
        "F",
        "Grade 1",
        "111.0",
        "19.7",
        "2024-08-15",
        "re-weighed",
    ],
    [
        "Bagumbayan ES",
        "SCH_0001",
        "136420010003",
        "DELA CRUZ, ANA",
        43262,
        "Lalaki",
        "Grade 2",
        "115.2",
        "21.0",
        "2024-08-15",
        "serial date in source",
    ],
    [
        "Bagumbayan ES",
        "SCH_0001",
        "136420010004",
        "GARCIA, JOSE M.",
        "2019-02-17 00:00:00",
        "2",
        "Grade 2",
        "117.9",
        "22.4",
        "2024-08-15",
        "exported from LIS",
    ],
    [
        "Bagumbayan ES",
        "SCH_0001",
        "",
        "MENDOZA, LIZA",
        "",
        "Babae",
        "Grade 1",
        "",
        "17.5",
        "2024-08-15",
        "no LRN yet",
    ],
    [
        "Bagumbayan ES",
        "SCH_0001",
        "136420010006",
        "AQUINO, PEDRO",
        "17/02/2019",
        "MALE",
        "Grade 3",
        "121.3",
        "24.8",
        "2024-08-15",
        "",
    ],
]

ENDLINE_ROWS: list[list[object]] = [
    [
        "Bagumbayan ES",
        "SCH_0001",
        "136420010001",
        "SANTOS, MARIA C.",
        "17-02-2019",
        "M",
        "Grade 1",
        "111.1",
        "19.4",
        "2025-03-20",
    ],
    [
        "Bagumbayan ES",
        "SCH_0001",
        "136420010002",
        "REYES, JUANA P.",
        "2019/01/02",
        "F",
        "Grade 1",
        "113.6",
        "20.9",
        "2025-03-20",
    ],
    [
        "Bagumbayan ES",
        "SCH_0001",
        "136420010004",
        "GARCIA, JOSE M.",
        "17 Feb 2019",
        "M",
        "Grade 2",
        "120.5",
        "23.8",
        "2025-03-20",
    ],
]


def write_csv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def write_xlsx(
    path: Path,
    header: list[str],
    rows: list[list[object]],
    *,
    sheet_name: str,
    title_rows: list[list[object]] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_name
    for title in title_rows or []:
        sheet.append(title)
    sheet.append(header)
    for row in rows:
        sheet.append(row)
    workbook.save(path)


def build() -> None:
    write_xlsx(
        FIXTURE_ROOT / "baseline" / "SCH_0001_baseline.xlsx",
        [
            "Name of School",
            "School ID",
            "LRN",
            "NAME OF LEARNER",
            "Date of Birth",
            "Sex",
            "Grade Level",
            "Height (cm)",
            "Weight (kg)",
            "Date Measured",
            # Not in the registry: must survive in raw_payload_json and be logged.
            "Remarks",
        ],
        BASELINE_ROWS,
        sheet_name="Masterlist",
        title_rows=[["SBFP BASELINE WEIGHING FORM — SY 2024-2025"], []],
    )

    # No sex column: a required field, but not a minimum-viable one, so the file is
    # ingested with a missing_required drift row rather than rejected.
    write_csv(
        FIXTURE_ROOT / "baseline" / "SCH_0002_baseline.csv",
        ["School", "Learner Name", "DOB", "Yr Level"],
        [
            ["Malinao ES", "TORRES, MIGUEL", "43262", "Grade 1"],
            ["Malinao ES", "LIM, CARMELA", "2019-06-11", "Grade 2"],
            ["Malinao ES", "OCAMPO, RITA", "not a date", "Grade 2"],
        ],
    )

    # No school and no learner name: minimum_viable is absent, so this file must fail.
    write_csv(
        FIXTURE_ROOT / "baseline" / "SCH_0003_baseline.csv",
        ["LRN", "DOB", "Gender"],
        [["136420030001", "2019-03-04", "M"]],
    )

    write_xlsx(
        FIXTURE_ROOT / "endline" / "SCH_0001_endline.xlsx",
        [
            "SCHOOL NAME",
            "SCHOOL_ID",
            "Learner Reference Number",
            "Student Name",
            "Birthdate",
            "Gender",
            "Grade",
            "HEIGHT_CM",
            "WEIGHT_KG",
            "Weighing Date",
        ],
        ENDLINE_ROWS,
        sheet_name="DATA",
    )

    write_csv(
        FIXTURE_ROOT / "enrollment" / "enrollment_sy2024_2025.csv",
        ["School", "SY", "Total Enrolment"],
        [
            ["Bagumbayan ES", "2024-2025", "412"],
            ["Malinao ES", "2024-2025", "268"],
        ],
    )

    write_csv(
        FIXTURE_ROOT / "allocation" / "allocation_sy2024_2025.csv",
        ["Name of School", "School Year", "No. of Beneficiaries", "No. of Tranches"],
        [
            ["Bagumbayan ES", "2024-2025", "380", "3"],
            ["Malinao ES", "2024-2025", "240", "2"],
        ],
    )

    write_xlsx(
        FIXTURE_ROOT / "reference" / "school_masterlist.xlsx",
        [
            "School Code",
            "SCHOOL NAME",
            "Schools Division",
            "City/Municipality",
            "Brgy",
            "Classification",
            "Is SBFP",
            "Matched Pair",
        ],
        [
            [
                "SCH_0001",
                "Bagumbayan ES",
                "Lanao del Sur II",
                "Wao",
                "Poblacion",
                "Rural",
                "SBFP",
                "PAIR_01",
            ],
            [
                "SCH_0002",
                "Malinao ES",
                "Lanao del Sur II",
                "Wao",
                "Malinao",
                "Rural",
                "Control",
                "PAIR_01",
            ],
        ],
        sheet_name="Sheet1",
    )


if __name__ == "__main__":
    build()
    print(f"Wrote fixtures to {FIXTURE_ROOT}")
