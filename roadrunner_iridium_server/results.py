from typing import Literal, Annotated
from pydantic import BaseModel, RootModel, Field, ConfigDict, ValidationError
from pydantic.alias_generators import to_camel

class BaseResult(BaseModel):
    model_config = ConfigDict(
        strict=True,
        validate_by_alias=True,
        validate_by_name=True,
        alias_generator=to_camel,
    )

    id: str

class LoadModelResult(BaseResult):
    type: Literal["loadModel"]
    floating_species: dict[str, float]
    boundary_species: dict[str, float]
    reactions: list[str]
    parameters: dict[str, float]

class TimeCourseResult(BaseResult):
    type: Literal["timeCourse"]
    column_names: list[str]
    rows: list[list[float]]

class SteadyStateResult(BaseResult):
    type: Literal["steadyState"]
    variable_values: dict[str, float]

Result = RootModel[
    Annotated[
        LoadModelResult | TimeCourseResult | SteadyStateResult,
        Field(discriminator="type"),
    ]
]
