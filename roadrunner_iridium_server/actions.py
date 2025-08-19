from typing import Literal, Annotated
from pydantic import BaseModel, RootModel, Field, ConfigDict, ValidationError
from pydantic.alias_generators import to_camel

model_config = ConfigDict(
    strict=True,
    validate_by_alias=True,
    validate_by_name=True,
    alias_generator=to_camel,
)

class BaseAction(BaseModel):
    model_config = model_config

    # Id of the action. Will be the same in the response, so the client
    # can recognize it.
    id: str

    # Antimony code associated with the action.
    # If not present, use the code from the last action.
    code: str | None = None

class LoadModelAction(BaseAction):
    type: Literal["loadModel"]

class ParameterScanOptions(BaseModel):
    model_config = model_config

    varying_parameter: str
    varying_parameter_value: float

class TimeCourseAction(BaseAction):
    type: Literal["timeCourse"]
    start_time: float
    end_time: float
    number_of_points: int
    reset_initial_conditions: bool
    selection_list: list[str]

    variable_values: dict[str, float]
    parameter_scan_options: ParameterScanOptions | None = None

class SteadyStateAction(BaseAction):
    type: Literal["steadyState"]
    variable_values: dict[str, float]
    parameter_scan_options: ParameterScanOptions | None = None

Action = RootModel[
    Annotated[
        LoadModelAction | TimeCourseAction | SteadyStateAction,
        Field(discriminator="type")
    ]
]
