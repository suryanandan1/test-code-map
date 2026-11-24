from pathlib import Path
import pandas as p
from rapidfuzz import fuzz, process
file_path = Path(__file__).parent / "data" / "test_master.xlsx"
fuzzy_threshold = 85
name_column = "Test Name"
code_column = "Test Code"

def normalize(text: str):
    return " ".join(str(text).split()).lower()

def load():
    if not file_path.exists():
        raise RuntimeError("Test Master file doesnot exist")

    df = p.read_excel(file_path).fillna("")
    tests = {}
    for i in range(len(df)):
        name = df[name_column][i]
        code = df[code_column][i]
        if name and code:
            tests[normalize(name)] = (name, code)

    return tests

tests_value = load()
test_name = list(tests_value.keys())

def find_code(description: str, threshold: int = fuzzy_threshold):
    key = normalize(description)
    if key in tests_value:
        name, code = tests_value[key]
        return name, code, 100.0

    match = process.extractOne(key, test_name, scorer= fuzz.WRatio, score_cutoff= threshold)
    
    if match is None:
        return None

    name, code = tests_value[match[0]]

    return name, code, round(match[1], 2)