from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

import loinc_code_mapping
import test_code_service

app = FastAPI(title="Test Description Mapping API", version="1.0.0")

SERVICES = {"local": test_code_service, "loinc": loinc_code_mapping}


class MapRequest(BaseModel):

    test_description: str = Field(..., min_length=1, examples=["Hemoglobin"])
    code_type: Literal["local", "loinc"]


class MapResponse(BaseModel):
    input_test: str
    matched_test: str
    code_type: Literal["local", "loinc"]
    code: str
    match_score: float


@app.post("/map-test", response_model=MapResponse)
def map_test(request: MapRequest) -> MapResponse:
    service = SERVICES[request.code_type]
    result = service.find_code(request.test_description)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No {request.code_type} code found for '{request.test_description}'. "
                "Try the full test name, or check the spelling."
            ),
        )

    matched_test, code, match_score = result
    return MapResponse(
        input_test=request.test_description,
        matched_test=matched_test,
        code_type=request.code_type,
        code=code,
        match_score=match_score,
    )
