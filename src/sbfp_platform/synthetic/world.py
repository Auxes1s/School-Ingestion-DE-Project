"""Make the clean schools, children, and health facts used as truth.

Two rules keep the final scores fair. First, only ``baseline_retention_rate`` of the
children get an end row. The rest truly left. Do not count them as links that were
missed, as set by spec §3.2.

Second, each child grows by at least ``MIN_HEIGHT_GAIN_CM``. This is well above the
height drop guard. Without this floor, clean random data could look like a flaw and
cause false alerts.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import numpy as np

from sbfp_platform.synthetic import names

# Ages at the start. The meal plan serves grade school children.
MIN_AGE_YEARS = 5
MAX_AGE_YEARS = 12

# Use these age and height terms to make each start height in cm. The fit is for children
# who tend to be short for their age, which is the group the meal plan aims to help.
HEIGHT_INTERCEPT_CM = 74.0
HEIGHT_SLOPE_CM_PER_YEAR = 6.1
HEIGHT_SD_CM = 5.2

# Draw BMI, then use height to get weight. This keeps both facts sound for one child.
BMI_MEAN = 15.4
BMI_SD = 1.7
BMI_MIN = 12.0
BMI_MAX = 21.5

# Keep draws well within the rule bounds in ``configs/dqa_rules.yml``. With no clip, a
# rare clean draw can look like a flaw in a large run. The end wave can add 7 cm and 4 kg,
# so leave room below each top bound.
HEIGHT_CLIP_CM = (88.0, 178.0)
WEIGHT_CLIP_KG = (11.5, 90.0)

# Growth in the seven months from start to end.
HEIGHT_GAIN_MEAN_CM = 3.6
HEIGHT_GAIN_SD_CM = 0.8
#: Floor on height gain, set by the worst case the height-decrease rule must survive.
#: Digit heaping rounds one wave to the nearest 5 cm, moving it down by at most 2.5 cm.
#: If exactly one of a child's two waves is heaped, the apparent change is at least
#: ``MIN_HEIGHT_GAIN_CM - 2.5``; at 1.8 that is -0.7 cm, inside the rule's 1.0 cm
#: tolerance. Lower this and honest children start registering as injected defects.
MIN_HEIGHT_GAIN_CM = 1.8
WEIGHT_GAIN_MEAN_KG = 1.5
WEIGHT_GAIN_SD_KG = 0.6
MIN_WEIGHT_GAIN_KG = 0.2

# Add a small gain for schools with meals so later tests have a trend to find. This is
# not based on a real study or a stated effect size.
TREATMENT_HEIGHT_GAIN_CM = 0.45
TREATMENT_WEIGHT_GAIN_KG = 0.30


@dataclass(frozen=True)
class School:
    school_id: str
    school_name: str
    division: str
    municipality: str
    barangay: str
    urban_rural: str
    treatment_status: int
    matched_pair_id: str
    # True when this school rounds height to 5 cm. Set it once per school so the rule is
    # the same in both waves and cannot make a false height drop.
    heaps_digits: bool = False


@dataclass
class Child:
    child_id: str
    lrn: str
    name: str
    birth_date: dt.date
    sex: str
    baseline_school_id: str
    endline_school_id: str | None
    attrited: bool
    transferred: bool
    grade: str
    measurements: dict[str, Measurement] = field(default_factory=dict)


@dataclass(frozen=True)
class Measurement:
    measured_on: dt.date
    height_cm: float
    weight_kg: float
    age_years: float


@dataclass(frozen=True)
class World:
    schools: list[School]
    children: list[Child]
    baseline_window: tuple[dt.date, dt.date]
    endline_window: tuple[dt.date, dt.date]
    school_year: str

    @property
    def schools_by_id(self) -> dict[str, School]:
        return {school.school_id: school for school in self.schools}


def _parse_window(window: dict[str, str]) -> tuple[dt.date, dt.date]:
    return dt.date.fromisoformat(window["start"]), dt.date.fromisoformat(window["end"])


def build_schools(
    rng: np.random.Generator, scale: dict[str, int], treatment_share: float, heaping_share: float
) -> list[School]:
    """Lay out the school frame, assigning treatment within matched pairs. Use this rule as shown."""
    n_schools = scale["schools"]
    n_divisions = scale["divisions"]
    n_municipalities = scale["municipalities"]

    divisions = [
        f"Division of {names.DIVISION_STEMS[i % len(names.DIVISION_STEMS)]}"
        for i in range(n_divisions)
    ]
    municipalities = [
        (names.MUNICIPALITY_STEMS[i % len(names.MUNICIPALITY_STEMS)], divisions[i % n_divisions])
        for i in range(n_municipalities)
    ]

    used_names: set[str] = set()
    drafts: list[dict] = []
    for index in range(n_schools):
        municipality, division = municipalities[index % n_municipalities]
        barangay = names.BARANGAY_STEMS[index % len(names.BARANGAY_STEMS)]
        suffix = names.SCHOOL_SUFFIXES[(index // len(names.BARANGAY_STEMS)) % 4]
        candidate = f"{barangay} {suffix}"
        bump = 2
        while candidate in used_names:
            candidate = f"{barangay} {suffix} Annex {bump}"
            bump += 1
        used_names.add(candidate)
        drafts.append(
            {
                "school_id": f"{100001 + index}",
                "school_name": candidate,
                "division": division,
                "municipality": municipality,
                "barangay": barangay,
                "urban_rural": "Urban" if index % 4 == 0 else "Rural",
            }
        )

    # Put each two schools in a pair and use a coin toss to pick the meal school. If one
    # school is left, use ``treatment_share`` so the full share stays fair.
    treatment = np.zeros(n_schools, dtype=int)
    pair_ids = [""] * n_schools
    for pair_index, start in enumerate(range(0, n_schools - 1, 2)):
        pair_ids[start] = pair_ids[start + 1] = f"PAIR-{pair_index + 1:03d}"
        treated_first = bool(rng.random() < treatment_share)
        treatment[start] = int(treated_first)
        treatment[start + 1] = int(not treated_first)
    if n_schools % 2 == 1:
        last = n_schools - 1
        pair_ids[last] = f"PAIR-{(n_schools // 2) + 1:03d}"
        treatment[last] = int(rng.random() < treatment_share)

    n_heaping = max(1, round(heaping_share * n_schools)) if n_schools else 0
    heaping = set(int(i) for i in rng.choice(n_schools, size=n_heaping, replace=False))

    return [
        School(
            school_id=draft["school_id"],
            school_name=draft["school_name"],
            division=draft["division"],
            municipality=draft["municipality"],
            barangay=draft["barangay"],
            urban_rural=draft["urban_rural"],
            treatment_status=int(treatment[index]),
            matched_pair_id=pair_ids[index],
            heaps_digits=index in heaping,
        )
        for index, draft in enumerate(drafts)
    ]


def _unique_lrns(rng: np.random.Generator, count: int) -> list[str]:
    """Draw count distinct 12-digit learner reference numbers. Use this rule as shown. Use this rule as shown."""
    found: set[int] = set()
    ordered: list[int] = []
    while len(ordered) < count:
        draw = rng.integers(10**11, 10**12, size=count - len(ordered) + 16)
        for value in draw:
            candidate = int(value)
            if candidate not in found:
                found.add(candidate)
                ordered.append(candidate)
                if len(ordered) == count:
                    break
    return [f"{value:012d}" for value in ordered]


def build_children(
    rng: np.random.Generator,
    schools: list[School],
    n_children: int,
    retention_rate: float,
    transfer_rate: float,
    baseline_window: tuple[dt.date, dt.date],
) -> list[Child]:
    """Draw the child population and decide who is retained, who attrites, who moves. Use this rule as shown."""
    n_schools = len(schools)
    # Keep the child sum exact, but let some schools be two or three times as large as
    # others. This makes the fake frame and school totals more true to life.
    weights = rng.dirichlet(np.full(n_schools, 6.0))
    counts = _apportion(weights, n_children)

    lrns = _unique_lrns(rng, n_children)
    sexes = np.where(rng.random(n_children) < 0.51, "Male", "Female")
    ages = rng.integers(MIN_AGE_YEARS, MAX_AGE_YEARS + 1, size=n_children)
    day_offsets = rng.integers(0, 365, size=n_children)

    baseline_start, _ = baseline_window
    school_of_child: list[str] = []
    for school, count in zip(schools, counts, strict=True):
        school_of_child.extend([school.school_id] * count)

    children: list[Child] = []
    for index in range(n_children):
        age = int(ages[index])
        # Start at the first day of the base wave, then take off age and a random day
        # shift. The child is age or age plus part of a year on test day.
        birth_date = baseline_start.replace(year=baseline_start.year - age) - dt.timedelta(
            days=int(day_offsets[index])
        )
        sex = str(sexes[index])
        children.append(
            Child(
                child_id=f"CH{index + 1:07d}",
                lrn=lrns[index],
                name=names.full_name(rng, sex),
                birth_date=birth_date,
                sex=sex,
                baseline_school_id=school_of_child[index],
                endline_school_id=None,
                attrited=True,
                transferred=False,
                grade=f"Grade {min(6, max(1, age - 4))}",
            )
        )

    _assign_followup(rng, children, schools, retention_rate, transfer_rate)
    return children


def _apportion(weights: np.ndarray, total: int) -> list[int]:
    """Split total across weights with largest-remainder, guaranteeing the sum. Use this rule as shown. Use this rule as shown."""
    raw = weights * total
    floors = np.floor(raw).astype(int)
    shortfall = total - int(floors.sum())
    if shortfall > 0:
        order = np.argsort(-(raw - floors), kind="stable")
        for position in order[:shortfall]:
            floors[position] += 1
    return [int(value) for value in floors]


def _assign_followup(
    rng: np.random.Generator,
    children: list[Child],
    schools: list[School],
    retention_rate: float,
    transfer_rate: float,
) -> None:
    n = len(children)
    n_retained = round(retention_rate * n)
    order = rng.permutation(n)
    retained = [int(i) for i in order[:n_retained]]

    n_transferred = round(transfer_rate * n_retained)
    transferred = set(retained[:n_transferred])
    school_ids = [school.school_id for school in schools]

    for index in retained:
        child = children[index]
        child.attrited = False
        if index in transferred and len(school_ids) > 1:
            alternatives = [sid for sid in school_ids if sid != child.baseline_school_id]
            child.endline_school_id = str(rng.choice(alternatives))
            child.transferred = True
        else:
            child.endline_school_id = child.baseline_school_id


def draw_measurements(
    rng: np.random.Generator,
    world_children: list[Child],
    schools_by_id: dict[str, School],
    baseline_window: tuple[dt.date, dt.date],
    endline_window: tuple[dt.date, dt.date],
    school_measurement_dates: dict[tuple[str, str], dt.date],
) -> None:
    """Attach baseline and endline health facts to every child, in place. Use this rule as shown."""
    n = len(world_children)
    height_noise = rng.normal(0.0, HEIGHT_SD_CM, size=n)
    bmi_draw = np.clip(rng.normal(BMI_MEAN, BMI_SD, size=n), BMI_MIN, BMI_MAX)
    height_gain = np.maximum(
        rng.normal(HEIGHT_GAIN_MEAN_CM, HEIGHT_GAIN_SD_CM, size=n), MIN_HEIGHT_GAIN_CM
    )
    weight_gain = np.maximum(
        rng.normal(WEIGHT_GAIN_MEAN_KG, WEIGHT_GAIN_SD_KG, size=n), MIN_WEIGHT_GAIN_KG
    )
    day_jitter_baseline = rng.integers(-3, 4, size=n)
    day_jitter_endline = rng.integers(-3, 4, size=n)

    for index, child in enumerate(world_children):
        baseline_date = _jitter(
            school_measurement_dates[(child.baseline_school_id, "baseline")],
            int(day_jitter_baseline[index]),
            baseline_window,
        )
        age_baseline = (baseline_date - child.birth_date).days / 365.25
        height = HEIGHT_INTERCEPT_CM + HEIGHT_SLOPE_CM_PER_YEAR * age_baseline
        height = _clip(height + height_noise[index], HEIGHT_CLIP_CM)
        weight = _clip(bmi_draw[index] * (height / 100.0) ** 2, WEIGHT_CLIP_KG)
        child.measurements["baseline"] = Measurement(
            measured_on=baseline_date,
            height_cm=round(height, 1),
            weight_kg=round(weight, 1),
            age_years=round(float(age_baseline), 2),
        )

        if child.attrited or child.endline_school_id is None:
            continue

        endline_date = _jitter(
            school_measurement_dates[(child.endline_school_id, "endline")],
            int(day_jitter_endline[index]),
            endline_window,
        )
        treated = schools_by_id[child.endline_school_id].treatment_status == 1
        gain_h = float(height_gain[index]) + (TREATMENT_HEIGHT_GAIN_CM if treated else 0.0)
        gain_w = float(weight_gain[index]) + (TREATMENT_WEIGHT_GAIN_KG if treated else 0.0)
        endline_height = child.measurements["baseline"].height_cm + gain_h
        endline_weight = child.measurements["baseline"].weight_kg + gain_w
        child.measurements["endline"] = Measurement(
            measured_on=endline_date,
            height_cm=round(endline_height, 1),
            weight_kg=round(endline_weight, 1),
            age_years=round((endline_date - child.birth_date).days / 365.25, 2),
        )


def _clip(value: float, bounds: tuple[float, float]) -> float:
    low, high = bounds
    return float(min(max(value, low), high))


def _jitter(anchor: dt.date, days: int, window: tuple[dt.date, dt.date]) -> dt.date:
    start, end = window
    return min(max(anchor + dt.timedelta(days=days), start), end)


def build_world(rng_factory, config) -> World:
    """Assemble the complete pre-flaw world for one run. Use this rule as shown."""
    scale = config.scale
    synthetic = config.synthetic
    baseline_window = _parse_window(config.project["baseline_window"])
    endline_window = _parse_window(config.project["endline_window"])

    schools = build_schools(
        rng_factory("world.schools"),
        scale,
        float(synthetic["treatment_share"]),
        float(config.issue_rates["digit_heaping"]),
    )

    children = build_children(
        rng_factory("world.children"),
        schools,
        int(scale["children"]),
        float(synthetic["baseline_retention_rate"]),
        float(synthetic["transfer_rate"]),
        baseline_window,
    )

    date_rng = rng_factory("world.measurement_dates")
    school_measurement_dates: dict[tuple[str, str], dt.date] = {}
    for school in schools:
        for period, window in (("baseline", baseline_window), ("endline", endline_window)):
            start, end = window
            span = (end - start).days
            offset = int(date_rng.integers(3, max(4, span - 3)))
            school_measurement_dates[(school.school_id, period)] = start + dt.timedelta(days=offset)

    draw_measurements(
        rng_factory("world.anthropometrics"),
        children,
        {school.school_id: school for school in schools},
        baseline_window,
        endline_window,
        school_measurement_dates,
    )

    return World(
        schools=schools,
        children=children,
        baseline_window=baseline_window,
        endline_window=endline_window,
        school_year=str(config.project["school_year"]),
    )
