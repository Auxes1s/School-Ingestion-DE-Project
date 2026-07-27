"""Name pools and the spelling drift that makes probabilistic linkage necessary.

The pools are deliberately small relative to the child count. Real enrollment lists
contain genuine name collisions between different children, and a generator that made
every name unique would hand the linkage layer a problem far easier than the one the
real pipeline faces — the measured precision would then be a flattering artifact of
the generator rather than a property of the matcher.

Every name written here is drawn from generic name pools and combined at random; none
refers to a real person.
"""

from __future__ import annotations

import numpy as np

SURNAMES = (
    "Dela Cruz",
    "Santos",
    "Reyes",
    "Ramos",
    "Mendoza",
    "Garcia",
    "Bautista",
    "Ocampo",
    "Torres",
    "Domingo",
    "Castillo",
    "Villanueva",
    "Aquino",
    "Fernandez",
    "Rivera",
    "Navarro",
    "Salazar",
    "Pascual",
    "Alonzo",
    "Gonzales",
    "Marcelo",
    "Espiritu",
    "Lacsamana",
    "Bagcal",
    "Malabanan",
    "Sarmiento",
    "Panganiban",
    "Balagtas",
    "Macaraeg",
    "Dimaculangan",
    "Abueva",
    "Cabrera",
    "Ilagan",
    "Quimpo",
    "Tolentino",
    "Zamora",
    "Andrada",
    "Batulan",
    "Camacho",
    "Dagohoy",
    "Ebreo",
    "Ferrer",
    "Guiam",
    "Hadjirul",
    "Ibrahim",
    "Jamiri",
    "Kalim",
    "Lantud",
    "Macalangan",
    "Nasser",
    "Omar",
    "Pangandaman",
    "Radiamoda",
    "Sarangani",
    "Tamano",
    "Usman",
)

GIVEN_NAMES_MALE = (
    "Juan",
    "Jose",
    "Miguel",
    "Carlo",
    "Angelo",
    "Rafael",
    "Nathaniel",
    "Emmanuel",
    "Christian",
    "Joshua",
    "Mark",
    "Paulo",
    "Dominic",
    "Gabriel",
    "Rommel",
    "Ferdinand",
    "Alfonso",
    "Benigno",
    "Eduardo",
    "Ignacio",
    "Norodin",
    "Alimudin",
    "Saidamin",
    "Cassim",
    "Datu",
    "Amir",
    "Hassan",
    "Yusuf",
)

GIVEN_NAMES_FEMALE = (
    "Maria",
    "Ana",
    "Jasmine",
    "Kristine",
    "Angelica",
    "Bernadette",
    "Catherine",
    "Divina",
    "Elena",
    "Faith",
    "Grace",
    "Hazel",
    "Imelda",
    "Josefina",
    "Kimberly",
    "Lorna",
    "Marilou",
    "Nerissa",
    "Ophelia",
    "Precious",
    "Rowena",
    "Sheila",
    "Norhaya",
    "Bai",
    "Sittie",
    "Farhana",
    "Johaira",
    "Rohaina",
)

MIDDLE_NAMES = (
    "Abad",
    "Bautista",
    "Cruz",
    "Diaz",
    "Estrada",
    "Flores",
    "Galang",
    "Hernandez",
    "Ibanez",
    "Jimenez",
    "Lopez",
    "Manalo",
    "Nolasco",
    "Ortega",
    "Perez",
    "Quinto",
    "Rosales",
    "Soriano",
    "Trinidad",
    "Ubaldo",
    "Valdez",
    "Yap",
)

#: Place-name stems for school and barangay names. Plausible in register, fictional in
#: fact — no real school in the modeled region is named here.
BARANGAY_STEMS = (
    "Malaya",
    "Bagong Silang",
    "Maharlika",
    "Poblacion",
    "San Isidro",
    "Santo Nino",
    "Bantayan",
    "Calumpang",
    "Dalipuga",
    "Ermita",
    "Fatima",
    "Guinhawa",
    "Hagonoy",
    "Ilaya",
    "Kalayaan",
    "Lumbac",
    "Marinaut",
    "Nangka",
    "Osmena",
    "Pantar",
    "Rizal",
    "Sagonsongan",
    "Tubod",
    "Ubos",
    "Vira",
    "Wawa",
    "Bubong",
    "Cadayonan",
    "Dansalan",
    "Ditsaan",
    "Gadongan",
    "Inudaran",
    "Kilala",
    "Linamon",
    "Matampay",
    "Pagalamatan",
    "Ramain",
    "Saguiaran",
    "Tagoloan",
    "Wato",
    "Basak",
    "Buadi",
    "Cormatan",
    "Dimayon",
    "Kapatagan",
    "Lilod",
    "Madaya",
    "Pindolonan",
    "Salvador",
    "Tamparan",
    "Bacolod",
    "Camague",
    "Dalama",
    "Kalilangan",
    "Lumbatan",
    "Masiu",
    "Pualas",
    "Sultan",
    "Taraka",
    "Wao",
)

SCHOOL_SUFFIXES = (
    "Elementary School",
    "Central Elementary School",
    "Primary School",
    "Integrated School",
)

MUNICIPALITY_STEMS = (
    "Balindong",
    "Bumbaran",
    "Calanogas",
    "Ditsaan-Ramain",
    "Ganassi",
    "Kapai",
    "Lumba-Bayabao",
    "Madalum",
    "Maguing",
    "Marantao",
    "Masiu",
    "Mulondo",
    "Piagapo",
    "Poona Bayabao",
    "Saguiaran",
    "Tagoloan II",
    "Tamparan",
    "Taraka",
    "Tubaran",
    "Wao",
)

DIVISION_STEMS = ("Lakandula", "Maharlika North", "Bagumbayan South")


def full_name(rng: np.random.Generator, sex: str) -> str:
    """Compose a name in the one format the generator ever writes.

    Format drift (``"Cruz, Juan"`` vs ``"Juan Cruz"``) would break deterministic linkage
    just as thoroughly as a spelling error, but it is not one of the configured defect
    types — so it would be an unrecorded defect and a guaranteed false positive in the
    scorecard. The generator therefore commits to ``"Surname, Given Middle"``
    everywhere, and lets :func:`drift_spelling` be the only source of name variation.
    """
    pool = GIVEN_NAMES_MALE if sex == "Male" else GIVEN_NAMES_FEMALE
    given = str(rng.choice(pool))
    middle = str(rng.choice(MIDDLE_NAMES))
    surname = str(rng.choice(SURNAMES))
    return f"{surname}, {given} {middle}"


#: Vowel confusions common in hand-transcribed lists.
_VOWEL_SWAPS = {"a": "e", "e": "a", "i": "e", "o": "u", "u": "o"}


def drift_spelling(rng: np.random.Generator, name: str) -> str:
    """Perturb a name the way a second data entry clerk would.

    Returns a string that differs from ``name``; if a transform happens to be a no-op
    the next one is tried, so the caller can rely on the value having actually changed.
    """
    transforms = (
        _transpose,
        _drop_letter,
        _double_letter,
        _swap_vowel,
        _middle_to_initial,
        _drop_middle,
    )
    order = rng.permutation(len(transforms))
    for index in order:
        candidate = transforms[int(index)](rng, name)
        if candidate and candidate != name:
            return candidate
    return name + "."


def _letter_positions(name: str) -> list[int]:
    return [i for i, ch in enumerate(name) if ch.isalpha()]


def _transpose(rng: np.random.Generator, name: str) -> str:
    positions = [i for i in _letter_positions(name) if i + 1 < len(name) and name[i + 1].isalpha()]
    if not positions:
        return name
    i = int(rng.choice(positions))
    return name[:i] + name[i + 1] + name[i] + name[i + 2 :]


def _drop_letter(rng: np.random.Generator, name: str) -> str:
    positions = [i for i in _letter_positions(name) if i > 0]
    if not positions:
        return name
    i = int(rng.choice(positions))
    return name[:i] + name[i + 1 :]


def _double_letter(rng: np.random.Generator, name: str) -> str:
    positions = _letter_positions(name)
    if not positions:
        return name
    i = int(rng.choice(positions))
    return name[: i + 1] + name[i] + name[i + 1 :]


def _swap_vowel(rng: np.random.Generator, name: str) -> str:
    positions = [i for i, ch in enumerate(name) if ch.lower() in _VOWEL_SWAPS and i > 0]
    if not positions:
        return name
    i = int(rng.choice(positions))
    replacement = _VOWEL_SWAPS[name[i].lower()]
    return name[:i] + (replacement.upper() if name[i].isupper() else replacement) + name[i + 1 :]


def _middle_to_initial(rng: np.random.Generator, name: str) -> str:
    parts = name.rsplit(" ", 1)
    if len(parts) != 2 or len(parts[1]) < 2:
        return name
    return f"{parts[0]} {parts[1][0]}."


def _drop_middle(rng: np.random.Generator, name: str) -> str:
    parts = name.rsplit(" ", 1)
    if len(parts) != 2:
        return name
    return parts[0]


def drift_school_name(rng: np.random.Generator, name: str) -> str:
    """Abbreviate a school name the way a submitting school actually types it."""
    candidates = [
        name.replace("Elementary School", "Elem. School"),
        name.replace("Elementary School", "ES"),
        name.replace("School", "Sch."),
        name.upper(),
        f"{name} (Main)",
    ]
    distinct = [c for c in candidates if c != name]
    if not distinct:
        return f"{name} ES"
    return str(rng.choice(distinct))
