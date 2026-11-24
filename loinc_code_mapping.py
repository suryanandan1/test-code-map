import re
from functools import lru_cache
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process

Match = tuple[str, str, float]


def normalize(text: str) -> str:
    return " ".join(str(text).split()).lower()


LOINC_FILE = Path(__file__).parent / "data" / "Loinc.csv"
FUZZY_THRESHOLD = 80
FUZZY_CANDIDATES_PER_COLUMN = 50
NAME_COLUMNS = ["COMPONENT", "SHORTNAME", "LONG_COMMON_NAME"]
SYNONYM_COLUMN = "RELATEDNAMES2"
NAME_TIER, SYNONYM_TIER = 0, 1
# name similarity is too noisy for very short queries, so those fall back to rank only
MIN_LENGTH_FOR_NAME_TIEBREAK = 8


def _variants(key: str):
    # "sgpt (alt)" -> "sgpt (alt)", "sgpt", "alt"
    yield key
    if "(" in key:
        outside = normalize(re.sub(r"\(.*?\)", " ", key))
        if outside and outside != key:
            yield outside
        for inside in re.findall(r"\((.*?)\)", key):
            inside = normalize(inside)
            if inside:
                yield inside


def _load() -> pd.DataFrame:
    if not LOINC_FILE.exists():
        raise RuntimeError(f"LOINC file not found: {LOINC_FILE}")

    columns = ["LOINC_NUM", "STATUS", "CLASSTYPE", "COMMON_TEST_RANK", SYNONYM_COLUMN, *NAME_COLUMNS]
    frame = pd.read_csv(LOINC_FILE, usecols=columns, dtype=str).fillna("")
    frame["rank"] = pd.to_numeric(frame["COMMON_TEST_RANK"], errors="coerce").fillna(0).astype(int)
    # active lab tests that are in the common test ranking
    keep = (frame["STATUS"] == "ACTIVE") & (frame["CLASSTYPE"] == "1") & (frame["rank"] > 0)
    return frame[keep].reset_index(drop=True)


_LOINC = _load()
_CODES = _LOINC["LOINC_NUM"].tolist()
_RANKS = _LOINC["rank"].tolist()
_NAMES = {column: _LOINC[column].tolist() for column in NAME_COLUMNS}
_SEARCHABLE = {column: [name.lower() for name in names] for column, names in _NAMES.items()}
_LONG_NAMES = _SEARCHABLE["LONG_COMMON_NAME"]


def _build_exact_index() -> dict[str, list[tuple[int, int, str]]]:
    index = {}
    synonyms = _LOINC[SYNONYM_COLUMN].tolist()
    for row in range(len(_LOINC)):
        names = [(NAME_TIER, _NAMES[column][row]) for column in NAME_COLUMNS]
        related = [(SYNONYM_TIER, part.strip()) for part in synonyms[row].split(";")]
        for tier, name in names + related:
            key = normalize(name)
            if key:
                index.setdefault(key, []).append((tier, row, name))
    return index


_EXACT = _build_exact_index()


def _ordering(key: str):
    if len(key) < MIN_LENGTH_FOR_NAME_TIEBREAK:
        return lambda row: (_RANKS[row],)
    return lambda row: (-fuzz.WRatio(key, _LONG_NAMES[row]), _RANKS[row])


def _closest(key: str, entries: list[tuple[int, int, str]]) -> tuple[int, str]:
    order = _ordering(key)
    _, row, name = min(entries, key=lambda entry: (entry[0], *order(entry[1])))
    return row, name


def _fuzzy_search(key: str, threshold: int) -> Match | None:
    best_per_row = {}  # row -> (score, column)
    for column, names in _SEARCHABLE.items():
        hits = process.extract(
            key, names, scorer=fuzz.WRatio, limit=FUZZY_CANDIDATES_PER_COLUMN, score_cutoff=threshold
        )
        for _, score, row in hits:
            if row not in best_per_row or score > best_per_row[row][0]:
                best_per_row[row] = (score, column)

    if not best_per_row:
        return None

    order = _ordering(key)
    row = min(best_per_row, key=lambda r: (-best_per_row[r][0], *order(r)))
    score, column = best_per_row[row]
    return _NAMES[column][row], _CODES[row], round(score, 2)


@lru_cache(maxsize=1024)
def find_code(description: str, threshold: int = FUZZY_THRESHOLD) -> Match | None:
    key = normalize(description)
    variants = list(_variants(key))

    for variant in variants:
        if variant in _EXACT:
            row, name = _closest(variant, _EXACT[variant])
            score = 100.0 if variant == key else round(fuzz.WRatio(key, normalize(name)), 2)
            return name, _CODES[row], score

    for variant in variants:
        match = _fuzzy_search(variant, threshold)
        if match is not None:
            return match
    return None
