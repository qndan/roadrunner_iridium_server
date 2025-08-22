from typing import Literal, Annotated
from pydantic import BaseModel, RootModel, Field, ConfigDict, ValidationError
from pydantic.alias_generators import to_camel

model_config = ConfigDict(
    strict=True,
    validate_by_alias=True,
    validate_by_name=True,
    alias_generator=to_camel,
)

class LoadModelResult(BaseModel):
    model_config = model_config

    floating_species: dict[str, float]
    boundary_species: dict[str, float]
    reactions: list[str]
    parameters: dict[str, float]

class TimeCourseResult(BaseModel):
    model_config = model_config

    column_names: list[str]
    rows: list[list[float]]

class SteadyStateResult(BaseModel):
    model_config = model_config

    variable_values: dict[str, float]

class Result(BaseModel):
    model_config = model_config

    id: int
    data: LoadModelResult | TimeCourseResult | SteadyStateResult

class ErrorResult(BaseModel):
    model_config = model_config

    id: int
    error_message: str
