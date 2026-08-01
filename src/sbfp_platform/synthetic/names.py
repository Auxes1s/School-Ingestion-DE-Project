"""Make fake names and the typos needed to test row links.

The name pools are small on purpose. Real school lists have two children with the same
name. If each test name were unique, the link task would be far too easy and its score
would look too good. Each name here is made at random from a broad pool. No name points
to a real child.
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

# Name stems for schools and towns. They sound real, but no real school has these names.
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
    """Compose a name in the one format the generator ever writes. Use this rule as shown."""
    pool = GIVEN_NAMES_MALE if sex == "Male" else GIVEN_NAMES_FEMALE
    given = str(rng.choice(pool))
    middle = str(rng.choice(MIDDLE_NAMES))
    surname = str(rng.choice(SURNAMES))
    return f"{surname}, {given} {middle}"


# Vowel swaps that are common in lists typed by hand.
_VOWEL_SWAPS = {"a": "e", "e": "a", "i": "e", "o": "u", "u": "o"}


def drift_spelling(rng: np.random.Generator, name: str) -> str:
    """Perturb spelling or token order the way a second form can record a name."""
    transforms = (
        _transpose,
        _drop_letter,
        _double_letter,
        _swap_vowel,
        _middle_to_initial,
        _drop_middle,
        _first_middle_last,
        _given_surname_only,
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


def _name_parts(name: str) -> tuple[str, str, str] | None:
    """Split the generator's canonical ``surname, given middle`` representation."""
    if "," not in name:
        return None
    surname, remainder = (part.strip() for part in name.split(",", 1))
    tokens = remainder.split()
    if not surname or len(tokens) < 2:
        return None
    return surname, tokens[0], " ".join(tokens[1:])


def _first_middle_last(rng: np.random.Generator, name: str) -> str:
    """Change ``Last, First Middle`` into the common ``First Middle Last`` form."""
    parts = _name_parts(name)
    if parts is None:
        return name
    surname, given, middle = parts
    return f"{given} {middle} {surname}"


def _given_surname_only(rng: np.random.Generator, name: str) -> str:
    """Drop the middle name and change token order at the same time."""
    parts = _name_parts(name)
    if parts is None:
        return name
    surname, given, _middle = parts
    return f"{given} {surname}"


def drift_school_name(rng: np.random.Generator, name: str) -> str:
    """Abbreviate a school name the way a submitting school actually types it. Use this rule as shown. Use this rule as shown."""
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
