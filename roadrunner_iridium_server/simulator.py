import warnings
import logging
from dataclasses import dataclass

import antimony
from roadrunner import RoadRunner

from .actions import ParameterScanOptions
from .results import LoadModelResult

logger = logging.getLogger(__name__)

REACTIONS = 6 # allReactions
FLOATING_SPECIES = 11 # varSpecies
BOUNDARY_SPECIES = 15 # constSpecies
PARAMETERS = 16 # constFormulas

class Simulator:
    # The antimony code
    code: str | None
    sbml: str | None
    _roadrunner: RoadRunner | None

    _cached_floating_species: dict[str, float]
    _cached_boundary_species: dict[str, float]
    _cached_reactions: list[str]
    _cached_parameters: dict[str, float]

    def __init__(self):
        self.code = None
        self.sbml = None
        self._roadrunner = None

    def load_code(self, code: str):
        """Load new code into the simulator.
        Subsequent method calls will use this code (e.g. `simulate_time_course` will simulate using this code).

        Throws ValueError on failure
        """
        self.code = code

        sbml = self._convert_antimony_to_sbml(code)
        self.sbml = sbml

        self._roadrunner = None # invalidate the current one

        self._cached_floating_species = self._collect_symbol_assignments(FLOATING_SPECIES)
        self._cached_boundary_species = self._collect_symbol_assignments(BOUNDARY_SPECIES)
        self._cached_reactions = self._collect_symbol_names(REACTIONS)
        self._cached_parameters = self._collect_symbol_assignments(PARAMETERS)

    @dataclass
    class ModelInfo:
        floating_species: dict[str, float]
        boundary_species: dict[str, float]
        reactions: list[str]
        parameters: dict[str, float]

    def get_model_info(self) -> ModelInfo:
        """Returns info about the model"""

        return Simulator.ModelInfo(
            floating_species=self._cached_floating_species,
            boundary_species=self._cached_boundary_species,
            reactions=self._cached_reactions,
            parameters=self._cached_parameters,
        )

    @dataclass 
    class TimeCourseResult:
        column_names: list[str]
        rows: list[list[float]]

    def simulate_time_course(
        self,
        start_time: float,
        end_time: float,
        number_of_points: int,
        reset_initial_conditions: bool,
        selection_list: list[str],
        variable_values: dict[str, float],
        parameter_scan_options: ParameterScanOptions | None = None,
    ) -> TimeCourseResult:
        logger.debug("Starting simulation")

        if not self._roadrunner:
            self._roadrunner = RoadRunner(self.sbml)

        # this is incorrect behavior when `reset_initial_conditions` is false
        # and `variable_values` are being changed.
        # for example, take this scenario:
        #  - user simulates with sliders A=5, B=20
        #  - disable reset_initial_conditions
        #  - user simulates with sliders A=10
        # B will stay 20 when it should reset to its initial value
        if reset_initial_conditions:
            self._roadrunner.resetToOrigin()

        model_keys = self._roadrunner.model.keys()
        for name, value in variable_values.items():
            if name in model_keys:
                self._roadrunner.setValue(name, value)

        if parameter_scan_options:
            if parameter_scan_options.varying_parameter in model_keys:
                self._roadrunner.model[
                    parameter_scan_options.varying_parameter
                ] = parameter_scan_options.varying_parameter_value

        result = self._roadrunner.simulate(
            start_time,
            end_time,
            number_of_points,
            selections=selection_list,
        )

        logging.debug("Simulation done")

        return Simulator.TimeCourseResult(
            column_names=result.colnames,
            rows=list(map(list, result)),
        )

    def _convert_antimony_to_sbml(self, code: str) -> str:
        """Throws ValueError if unable to convert"""

        load_status = antimony.loadAntimonyString(code)
        conversion_warnings = antimony.getSBMLWarnings()

        if conversion_warnings:
            warnings.warn(conversion_warnings)

        if load_status > 0:
            return antimony.getSBMLString()
        else:
            raise ValueError(antimony.getLastError())

    def _collect_symbol_names(self, type: int) -> list[str]:
        """Return a list of symbol names (in the loaded model) of the given type"""

        main_module_name = antimony.getMainModuleName()
        num = antimony.getNumSymbolsOfType(main_module_name, type)
        result = []
        for i in range(num):
            result.append(antimony.getNthSymbolNameOfType(main_module_name, type, i))
        return result

    def _collect_symbol_assignments(self, type: int) -> dict[str, float]:
        """Return a dict of {symbol names: initial assignment} (in the loaded model) of the given type"""

        main_module_name = antimony.getMainModuleName()
        num = antimony.getNumSymbolsOfType(main_module_name, type)
        result = {}
        for i in range(num):
            # probably going to break if it is a non-constant initial assignment
            result[
                antimony.getNthSymbolNameOfType(main_module_name, type, i)
            ] = float(
                antimony.getNthSymbolInitialAssignmentOfType(main_module_name, type, i)
            )
        return result

