from typing import Any
import warnings
import logging
from dataclasses import dataclass

import antimony
from roadrunner import RoadRunner, roadrunner

from .actions import ParameterScanOptions
from .results import (
    LoadModelResult,
    TimeCourseResult,
    SteadyStateResult, SteadyStateConcentration, SteadyStateResultItem
)

logger = logging.getLogger(__name__)

REACTIONS = 6 # allReactions
FLOATING_SPECIES = 11 # varSpecies
BOUNDARY_SPECIES = 15 # constSpecies
PARAMETERS = 16 # constFormulas

def named_array_to_result_item(named_array: Any) -> SteadyStateResultItem:
    return SteadyStateResultItem(
        rows=named_array.rownames,
        columns=named_array.colnames,
        values=list(named_array.view())
    )

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
        if self.code == code:
            return

        self.code = code

        sbml = self._convert_antimony_to_sbml(code)
        self.sbml = sbml

        self._roadrunner = RoadRunner(self.sbml)

        self._cached_floating_species = {}
        for (id, value) in zip(self._roadrunner.model.getFloatingSpeciesIds(), self._roadrunner.model.getFloatingSpeciesConcentrations()):
            self._cached_floating_species[id] = value

        self._cached_boundary_species = {}
        for (id, value) in zip(self._roadrunner.model.getBoundarySpeciesIds(), self._roadrunner.model.getBoundarySpeciesConcentrations()):
            self._cached_boundary_species[id] = value

        self._cached_reactions = list(self._roadrunner.model.getReactionIds())
        
        self._cached_parameters = {}
        for (id, value) in zip(self._roadrunner.model.getGlobalParameterIds(), self._roadrunner.model.getGlobalParameterValues()):
            self._cached_parameters[id] = value

    def get_model_info(self) -> LoadModelResult:
        """Returns info about the model"""

        return LoadModelResult(
            floating_species=self._cached_floating_species,
            boundary_species=self._cached_boundary_species,
            reactions=self._cached_reactions,
            parameters=self._cached_parameters,
        )

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

        # this is incorrect behavior when `reset_initial_conditions` is false
        # and `variable_values` are being changed.
        # for example, take this scenario:
        #  - user simulates with sliders A=5, B=20
        #  - disable reset_initial_conditions
        #  - user simulates with sliders A=10
        # B will stay 20 when it should reset to its initial value
        if reset_initial_conditions:
            self._roadrunner.resetAll()

        self._set_variables(variable_values, parameter_scan_options)

        result = self._roadrunner.simulate(
            start_time,
            end_time,
            number_of_points,
            selections=selection_list,
        )

        logger.debug("Simulation done")

        return TimeCourseResult(
            column_names=result.colnames,
            rows=list(map(list, result)),
        )

    def compute_steady_state(
        self,
        variable_values: dict[str, float],
        parameter_scan_options: ParameterScanOptions | None = None,
    ) -> SteadyStateResult:
        logger.debug("Starting steady state")

        if not self._roadrunner:
            self._roadrunner = RoadRunner(self.sbml)

        self._roadrunner.resetAll()
        self._set_variables(variable_values, parameter_scan_options)

        concentrations = []
        for (name, value) in zip(self._roadrunner.steadyStateSelections, self._roadrunner.getSteadyStateValues()):
            concentrations.append(SteadyStateConcentration(name=name, value=value))

        eigen_values = []
        for v in self._roadrunner.getFullEigenValues():
            eigen_values.append((v.real, v.imag))

        elasticities = named_array_to_result_item(self._roadrunner.getScaledElasticityMatrix()) # the order of this is important because for whatever reason some values become nan when the order is off
        concentration_control = named_array_to_result_item(self._roadrunner.getScaledConcentrationControlCoefficientMatrix())
        flux_control = named_array_to_result_item(self._roadrunner.getScaledFluxControlCoefficientMatrix())
        jacobian = named_array_to_result_item(self._roadrunner.getFullJacobian())

        logger.debug("Steady state done")

        return SteadyStateResult(
            value=self._roadrunner.steadyState(),
            concentrations=concentrations,
            eigen_values=eigen_values,
            jacobian=jacobian,
            concentration_control=concentration_control,
            flux_control=flux_control,
            elasticities=elasticities,
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

    def _set_variables(
        self,
        variable_values: dict[str, float],
        parameter_scan_options: ParameterScanOptions
    ):
        model_keys = self._roadrunner.model.keys()
        for name, value in variable_values.items():
            if name in model_keys:
                self._roadrunner.setValue(name, value)

        if parameter_scan_options:
            if parameter_scan_options.varying_parameter in model_keys:
                self._roadrunner.model[
                    parameter_scan_options.varying_parameter
                ] = parameter_scan_options.varying_parameter_value


