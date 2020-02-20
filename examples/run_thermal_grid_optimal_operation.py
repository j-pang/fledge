"""Example script for setting up and solving an thermal grid optimal operation problem."""

import numpy as np
import pandas as pd
import pyomo.environ as pyo

import fledge.config
import fledge.database_interface
import fledge.thermal_grid_models


def main():

    # Settings.
    scenario_name = "singapore_tanjongpagar"

    # Obtain data.
    scenario_data = fledge.database_interface.ScenarioData(scenario_name)

    # Obtain model.
    thermal_grid_model = fledge.thermal_grid_models.ThermalGridModel(scenario_name)

    # Instantiate optimization problem.
    optimization_problem = pyo.ConcreteModel()

    # Define variables.
    thermal_grid_model.define_optimization_variables(optimization_problem, scenario_data.timesteps)

    # Define DER constraints.
    # TODO: Arbitrary constraints to demonstrate the functionality.
    optimization_problem.der_constraints = pyo.ConstraintList()
    for timestep in scenario_data.timesteps:
        for der_index, der in enumerate(thermal_grid_model.ders):
            optimization_problem.der_constraints.add(
                optimization_problem.der_thermal_power_vector[timestep, der]
                >=
                0.5 * thermal_grid_model.der_thermal_power_vector_nominal[der_index]
            )
            optimization_problem.der_constraints.add(
                optimization_problem.der_thermal_power_vector[timestep, der]
                <=
                1.0 * thermal_grid_model.der_thermal_power_vector_nominal[der_index]
            )

    # Define thermal grid constraints.
    thermal_grid_model.define_optimization_constraints(optimization_problem, scenario_data.timesteps)

    # Define objective.
    cost = 0.0
    cost += (
        sum(
            optimization_problem.source_flow[timestep]
            for timestep in scenario_data.timesteps
        )
    )
    optimization_problem.objective = (
        pyo.Objective(
            expr=cost,
            sense=pyo.minimize
        )
    )

    # Solve optimization problem.
    optimization_solver = pyo.SolverFactory(fledge.config.solver_name)
    optimization_result = optimization_solver.solve(optimization_problem, tee=fledge.config.solver_output)
    if optimization_result.solver.termination_condition is not pyo.TerminationCondition.optimal:
        raise Exception(f"Invalid solver termination condition: {optimization_result.solver.termination_condition}")
    # optimization_problem.display()

    # Obtain results.
    (
        der_thermal_power_vector,
        branch_flow_vector,
        source_flow
    ) = thermal_grid_model.get_optimization_results(optimization_problem, scenario_data.timesteps)

    # Print some results.
    print(f"der_thermal_power_vector = \n{der_thermal_power_vector.to_string()}")
    print(f"branch_flow_vector = \n{branch_flow_vector.to_string()}")
    print(f"source_flow = \n{source_flow.to_string()}")


if __name__ == "__main__":
    main()