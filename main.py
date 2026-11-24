from typing import Literal
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import loinc_code_mapping
import test_code_service

app = FastAPI(title="Test Description Mapping API", version="1.0.0")
services = {"local": test_code_service, "loinc": loinc_code_mapping}

class MapRequest(BaseModel):
    test_description: str = Field(..., min_length=1)
    code_type: Literal["local", "loinc"]

class MapResponse(BaseModel):
    input_test: str
    matched_test: str
    code_type: str
    code: str
    match_score: float

@app.post("/map-test", response_model=MapResponse)
def map_test(request: MapRequest):
    service = services[request.code_type]
    result = service.find_code(request.test_description)
    if result is None:
        raise HTTPException(status_code=404, detail="No matching test code found")

    name = result[0]
    code = result[1]
    score = result[2]
    return MapResponse(input_test=request.test_description, matched_test=name, code_type=request.code_type, code=str(code), match_score=score)
