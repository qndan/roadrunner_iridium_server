from typing import Literal, Annotated
from pydantic import BaseModel, RootModel, Field, ConfigDict, ValidationError
from pydantic.alias_generators import to_camel

class BaseResponse(BaseModel):
    model_config = ConfigDict(
        strict=True,
        validate_by_alias=True,
        validate_by_name=True,
        alias_generator=to_camel,
    )

    id: str

class LoadModelResponse(BaseResponse):
    type: Literal["loadModel"]
    floating_species: dict[str, float]
    boundary_species: dict[str, float]
    reactions: list[str]
    parameters: dict[str, float]

class TimeCourseResponse(BaseResponse):
    type: Literal["timeCourse"]
    column_names: list[str]
    rows: list[list[float]]

class SteadyStateResponse(BaseResponse):
    type: Literal["steadyState"]
    variable_values: dict[str, float]

Response = RootModel[
    Annotated[
        LoadModelResponse | TimeCourseResponse | SteadyStateResponse,
        Field(discriminator="type"),
    ]
]
