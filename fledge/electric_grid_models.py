"""Electric grid models."""

import numpy as np
import pandas as pd
import scipy.sparse

import fledge.config
import fledge.database_interface

logger = fledge.config.get_logger(__name__)


class ElectricGridIndex(object):
    """Electric grid index object."""

    node_dimension: int
    branch_dimension: int
    load_dimension: int
    phases: pd.Index
    node_names: pd.Index
    node_types: pd.Index
    nodes_phases: pd.Index
    line_names: pd.Index
    transformer_names: pd.Index
    branch_names: pd.Index
    branch_types: pd.Index
    branches_phases: pd.Index
    load_names: pd.Index
    node_by_node_name: dict
    node_by_phase: dict
    node_by_node_type: dict
    node_by_load_name: dict
    branch_by_line_name: dict
    branch_by_transformer_name: dict
    branch_by_phase: dict
    load_by_load_name: dict

    def __init__(
            self,
            electric_grid_data: fledge.database_interface.ElectricGridData = None,
            scenario_name: str = None
    ):
        """Instantiate electric grid index object for given `electric_grid_data` or `scenario_name`."""

        # Load electric grid data, if none.
        if electric_grid_data is None:
            electric_grid_data = fledge.database_interface.ElectricGridData(scenario_name)

        # Obtain transformers for one / first winding.
        electric_grid_transformers_one_winding = (
            electric_grid_data.electric_grid_transformers.loc[
            electric_grid_data.electric_grid_transformers['winding'] == 1,
            :
            ]
        )

        # Define node dimension, i.e., number of phases of all nodes, which
        # will be the dimension of the nodal admittance matrix.
        # - The admittance matrix has one entry for each phase of each node in
        #   both dimensions.
        # - There cannot be "empty" dimensions for missing phases of nodes,
        #   because the matrix would become singular.
        # - Therefore the admittance matrix must have the exact number of existing
        #   phases of all nodes.
        self.node_dimension = (
            electric_grid_data.electric_grid_nodes.loc[
                :,
                [
                    'is_phase_1_connected',
                    'is_phase_2_connected',
                    'is_phase_3_connected'
                ]
            ].sum().sum()
        )

        # Define branch dimension, i.e., number of phases of all branches, which
        # will be the first dimension of the branch admittance matrices.
        # - Branches consider all power delivery elements, i.e., lines as well as
        #   transformers.
        # - The second dimension of the branch admittance matrices is the number of
        #   phases of all nodes.
        # - TODO: Add switches.
        line_dimension = (
            electric_grid_data.electric_grid_lines.loc[
            :,
            [
                'is_phase_1_connected',
                'is_phase_2_connected',
                'is_phase_3_connected'
            ]
            ].sum().sum()
        )
        transformer_dimension = (
            electric_grid_transformers_one_winding.loc[
                :,
                [
                    'is_phase_1_connected',
                    'is_phase_2_connected',
                    'is_phase_3_connected'
                ]
            ].sum().sum()
        )
        self.branch_dimension = line_dimension + transformer_dimension

        # Define load dimension, i.e., number of all loads, which
        # will be the second dimension of the load incidence matrix.
        self.load_dimension = (
            electric_grid_data.electric_grid_loads.shape[0]
        )

        # Create `nodes` data frame, i.e., collection of all phases of all nodes
        # for generating indexing functions for the admittance matrix.
        nodes = (
            pd.DataFrame(
                None,
                index=range(self.node_dimension),
                columns=[
                    'node_name',
                    'phase',
                    'node_type'
                ]
            )
        )
        # Fill `node_name`.
        nodes['node_name'] = (
            pd.concat([
                electric_grid_data.electric_grid_nodes.loc[
                    electric_grid_data.electric_grid_nodes['is_phase_1_connected'] == 1,
                    'node_name'
                ],
                electric_grid_data.electric_grid_nodes.loc[
                    electric_grid_data.electric_grid_nodes['is_phase_2_connected'] == 1,
                    'node_name'
                ],
                electric_grid_data.electric_grid_nodes.loc[
                    electric_grid_data.electric_grid_nodes['is_phase_3_connected'] == 1,
                    'node_name'
                ]
            ], ignore_index=True)
        )
        # Fill `phase`.
        nodes['phase'] = (
            np.concatenate([
                np.repeat('1', sum(electric_grid_data.electric_grid_nodes['is_phase_1_connected'] == 1)),
                np.repeat('2', sum(electric_grid_data.electric_grid_nodes['is_phase_2_connected'] == 1)),
                np.repeat('3', sum(electric_grid_data.electric_grid_nodes['is_phase_3_connected'] == 1))
            ])
        )
        # Fill `node_type`.
        nodes['node_type'] = 'no_source'
        # Set `node_type` for source node.
        nodes.loc[
            nodes['node_name'] == (electric_grid_data.electric_grids['source_node_name'][0]),
            'node_type'
        ] = 'source'
        # TODO: Sort nodes

        # Create `branches` data frame, i.e., collection of phases of all branches
        # for generating indexing functions for the branch admittance matrices.
        # - Transformers must have same number of phases per winding and exactly
        #   two windings.
        branches = (
            pd.DataFrame(
                None,
                index=range(self.branch_dimension),
                columns=[
                    'branch_name',
                    'phase',
                    'branch_type'
                ]
            )
        )
        # Fill `branch_name`.
        branches['branch_name'] = (
            pd.concat([
                electric_grid_data.electric_grid_lines.loc[
                    electric_grid_data.electric_grid_lines['is_phase_1_connected'] == 1,
                    'line_name'
                ],
                electric_grid_data.electric_grid_lines.loc[
                    electric_grid_data.electric_grid_lines['is_phase_2_connected'] == 1,
                    'line_name'
                ],
                electric_grid_data.electric_grid_lines.loc[
                    electric_grid_data.electric_grid_lines['is_phase_3_connected'] == 1,
                    'line_name'
                ],
                electric_grid_transformers_one_winding.loc[
                    electric_grid_transformers_one_winding['is_phase_1_connected'] == 1,
                    'transformer_name'
                ],
                electric_grid_transformers_one_winding.loc[
                    electric_grid_transformers_one_winding['is_phase_2_connected'] == 1,
                    'transformer_name'
                ],
                electric_grid_transformers_one_winding.loc[
                    electric_grid_transformers_one_winding['is_phase_3_connected'] == 1,
                    'transformer_name'
                ]
            ], ignore_index=True)
        )
        # Fill `phase`.
        branches['phase'] = (
            np.concatenate([
                np.repeat('1', sum(electric_grid_data.electric_grid_lines['is_phase_1_connected'] == 1)),
                np.repeat('2', sum(electric_grid_data.electric_grid_lines['is_phase_2_connected'] == 1)),
                np.repeat('3', sum(electric_grid_data.electric_grid_lines['is_phase_3_connected'] == 1)),
                np.repeat('1', sum(electric_grid_transformers_one_winding['is_phase_1_connected'] == 1)),
                np.repeat('2', sum(electric_grid_transformers_one_winding['is_phase_2_connected'] == 1)),
                np.repeat('3', sum(electric_grid_transformers_one_winding['is_phase_3_connected'] == 1))
            ])
        )
        # Fill `branch_type`.
        branches['branch_type'] = (
            np.concatenate([
                np.repeat('line', line_dimension),
                np.repeat('transformer', transformer_dimension)
            ])
        )
        # TODO: Sort branches

        # Define index vectors for various element types
        # for easier index definitions, e.g., in the optimization problem.
        self.phases = pd.Index(['1', '2', '3'])
        self.node_names = pd.Index(electric_grid_data.electric_grid_nodes['node_name'])
        self.node_types = pd.Index(['source', 'no_source'])
        self.nodes_phases = pd.Index(zip(nodes['node_name'], nodes['phase']))
        self.line_names = pd.Index(electric_grid_data.electric_grid_lines['line_name'])
        self.transformer_names = pd.Index(electric_grid_transformers_one_winding['transformer_name'])
        self.branch_names = pd.Index(branches['branch_name'])
        self.branch_types = pd.Index(['line', 'transformer'])
        self.branches_phases = pd.Index(zip(branches['branch_name'], branches['phase'], branches['branch_type']))
        self.load_names = pd.Index(electric_grid_data.electric_grid_loads['load_name'])

        # Generate indexing dictionaries for the nodal admittance matrix,
        # i.e., for all phases of all nodes.
        # - This is a workaround to avoid low-performance string search operations
        #   for each indexing access.
        # - Instead, the appropriate boolean index vectors are pre-generated here
        #   and stored into data frames.

        # Index by node name.
        self.node_by_node_name = dict.fromkeys(self.node_names)
        for node_name in self.node_names:
            self.node_by_node_name[node_name] = np.nonzero(nodes['node_name'] == node_name)[0].tolist()
        # Index by phase.
        self.node_by_phase = dict.fromkeys(self.phases)
        for phase in self.phases:
            self.node_by_phase[phase] = np.nonzero(nodes['phase'] == phase)[0].tolist()
        # Index by node type.
        self.node_by_node_type = dict.fromkeys(self.node_types)
        for node_type in self.node_types:
            self.node_by_node_type[node_type] = np.nonzero(nodes['node_type'] == node_type)[0].tolist()
        # Index by load name.
        self.node_by_load_name = dict.fromkeys(self.load_names)
        # TODO: Find a more efficient way to represent load / node / phase comparison.
        for load_name in self.load_names:
            load_phases = (
                np.where(
                    [
                        electric_grid_data.electric_grid_loads.at[load_name, 'is_phase_1_connected'] == 1,
                        electric_grid_data.electric_grid_loads.at[load_name, 'is_phase_2_connected'] == 1,
                        electric_grid_data.electric_grid_loads.at[load_name, 'is_phase_3_connected'] == 1
                    ],
                    ['1', '2', '3'],
                    [None, None, None]
                )
            )
            self.node_by_load_name[load_name] = (
                np.nonzero(
                    (nodes['node_name'] == electric_grid_data.electric_grid_loads.at[load_name, 'node_name'])
                    & (nodes['phase'].isin(load_phases))
                )[0].tolist()
            )

        # Generate indexing dictionaries for the branch admittance matrices,
        # i.e., for all phases of all branches.
        # - This is a workaround to avoid low-performance string search operations
        #   for each indexing access.
        # - Instead, the appropriate boolean index vectors are pre-generated here
        #   and stored into data frames.

        # Index by line name.
        self.branch_by_line_name = dict.fromkeys(self.line_names)
        for line_name in self.line_names:
            self.branch_by_line_name[line_name] = (
                np.nonzero(
                    (branches['branch_name'] == line_name)
                    & (branches['branch_type'] == 'line')
                )[0].tolist()
            )
        # Index by transformer name.
        self.branch_by_transformer_name = dict.fromkeys(self.transformer_names)
        for transformer_name in self.transformer_names:
            self.branch_by_line_name[transformer_name] = (
                np.nonzero(
                    (branches['branch_name'] == transformer_name)
                    & (branches['branch_type'] == 'transformer')
                )[0].tolist()
            )
        # Index by phase.
        self.branch_by_phase = dict.fromkeys(self.phases)
        for phase in self.phases:
            self.branch_by_phase[phase] = np.nonzero(branches['phase'] == phase)[0].tolist()

        # Generate indexing dictionary for the load incidence matrix.

        # Index by load name.
        self.load_by_load_name = dict(zip(self.load_names, range(len(self.load_names))))


class ElectricGridModel(object):
    """Electric grid model object."""

    electric_grid_data: fledge.database_interface.ElectricGridData
    index: ElectricGridIndex
    node_admittance_matrix: scipy.sparse.dok_matrix
    node_transformation_matrix: scipy.sparse.dok_matrix
    branch_admittance_1_matrix: scipy.sparse.dok_matrix
    branch_admittance_2_matrix: scipy.sparse.dok_matrix
    branch_incidence_1_matrix: scipy.sparse.dok_matrix
    branch_incidence_2_matrix: scipy.sparse.dok_matrix
    load_incidence_wye_matrix: scipy.sparse.dok_matrix
    load_incidence_delta_matrix: scipy.sparse.dok_matrix
    node_voltage_vector_no_load: np.ndarray
    load_power_vector_nominal: np.ndarray

    def __init__(
            self,
            electric_grid_data: fledge.database_interface.ElectricGridData = None,
            scenario_name: str = None
    ):
        """Instantiate electric grid model object for given `electric_grid_data` or `scenario_name`.

        - The nodal no-load voltage vector can be constructed by
          1) `voltage_no_load_method="by_definition"`, i.e., the nodal voltage
          definition in the database is taken, or by
          2) `voltage_no_load_method="by_calculation"`, i.e., the no-load voltage is
          calculated from the source node voltage and the nodal admittance matrix.
        """

        # Load electric grid data, if none.
        if electric_grid_data is None:
            electric_grid_data = fledge.database_interface.ElectricGridData(scenario_name)

        # Obtain electric grid index.
        self.index = ElectricGridIndex(electric_grid_data)

        # Define sparse matrices for nodal admittance, nodal transformation,
        # branch admittance, branch incidence and load matrix matrix entries.
        self.node_admittance_matrix = (
             scipy.sparse.dok_matrix((self.index.node_dimension, self.index.node_dimension), dtype=np.complex)
        )
        self.node_transformation_matrix = (
             scipy.sparse.dok_matrix((self.index.node_dimension, self.index.node_dimension), dtype=np.int)
        )
        self.branch_admittance_1_matrix = (
             scipy.sparse.dok_matrix((self.index.branch_dimension, self.index.node_dimension), dtype=np.complex)
        )
        self.branch_admittance_2_matrix = (
             scipy.sparse.dok_matrix((self.index.branch_dimension, self.index.node_dimension), dtype=np.complex)
        )
        self.branch_incidence_1_matrix = (
             scipy.sparse.dok_matrix((self.index.branch_dimension, self.index.node_dimension), dtype=np.int)
        )
        self.branch_incidence_2_matrix = (
             scipy.sparse.dok_matrix((self.index.branch_dimension, self.index.node_dimension), dtype=np.int)
        )
        self.load_incidence_wye_matrix = (
             scipy.sparse.dok_matrix((self.index.node_dimension, self.index.load_dimension), dtype=np.float)
        )
        self.load_incidence_delta_matrix = (
             scipy.sparse.dok_matrix((self.index.node_dimension, self.index.load_dimension), dtype=np.float)
        )

        # Define utility function to insert sub matrix into a sparse matrix at given row/column indexes.
        # - Ensures that values are added element-by-element to support sparse matrices.
        def insert_sub_matrix(matrix, sub_matrix, row_indexes, col_indexes):
            for row, sub_matrix_row in zip(row_indexes, sub_matrix.tolist()):
                for col, value in zip(col_indexes, sub_matrix_row):
                    matrix[row, col] += value  # In-place operator `+=` and empty return value for better performance.
            return

        # Add lines to admittance, transformation and incidence matrices.
        for line_index, line in electric_grid_data.electric_grid_lines.iterrows():
            # Obtain line resistance and reactance matrix entries for the line.
            rxc_matrix_entries_index = (
                electric_grid_data.electric_grid_line_types_matrices.loc[:, 'line_type'] == line['line_type']
            )
            r_matrix_entries = (
                electric_grid_data.electric_grid_line_types_matrices.loc[rxc_matrix_entries_index, 'r'].values
            )
            x_matrix_entries = (
                electric_grid_data.electric_grid_line_types_matrices.loc[rxc_matrix_entries_index, 'x'].values
            )
            c_matrix_entries = (
                electric_grid_data.electric_grid_line_types_matrices.loc[rxc_matrix_entries_index, 'c'].values
            )

            # Obtain the full line resistance and reactance matrices.
            # Data only contains upper half entries.
            rxc_matrix_full_index = (
                np.array([
                    [1, 2, 4],
                    [2, 3, 5],
                    [4, 5, 6]
                ]) - 1
            )
            # TODO: Remove usage of n_phases.
            rxc_matrix_full_index = (
                rxc_matrix_full_index[:line['n_phases'], :line['n_phases']]
            )
            r_matrix = r_matrix_entries[rxc_matrix_full_index]
            x_matrix = x_matrix_entries[rxc_matrix_full_index]
            c_matrix = c_matrix_entries[rxc_matrix_full_index]

            # Construct line series admittance matrix.
            series_admittance_matrix = (
                np.linalg.inv(
                    (r_matrix + 1j * x_matrix)
                    * line['length']
                )
            )

            # Construct line shunt admittance.
            # Note: nF to Ω with X = 1 / (2π * f * C)
            # TODO: Check line shunt admittance.
            base_frequency = 60.0  # TODO: Define base frequency in the database
            shunt_admittance_matrix = (
                c_matrix
                * 2 * np.pi * base_frequency * 1e-9
                * 0.5j
                * line['length']
            )

            # Construct line element admittance matrices according to:
            # https://doi.org/10.1109/TPWRS.2017.2728618
            admittance_matrix_11 = (
                series_admittance_matrix
                + shunt_admittance_matrix
            )
            admittance_matrix_12 = (
                - series_admittance_matrix
            )
            admittance_matrix_21 = (
                - series_admittance_matrix
            )
            admittance_matrix_22 = (
                series_admittance_matrix
                + shunt_admittance_matrix
            )

            # Obtain indexes for positioning the line element matrices
            # in the full admittance matrices.
            node_index_1 = (
                self.index.node_by_node_name[line['node_1_name']]
            )
            node_index_2 = (
                self.index.node_by_node_name[line['node_2_name']]
            )
            branch_index = (
                self.index.branch_by_line_name[line['line_name']]
            )

            # Add line element matrices to the nodal admittance matrix.
            insert_sub_matrix(
                self.node_admittance_matrix,
                admittance_matrix_11,
                node_index_1,
                node_index_1
            )
            insert_sub_matrix(
                self.node_admittance_matrix,
                admittance_matrix_12,
                node_index_1,
                node_index_2
            )
            insert_sub_matrix(
                self.node_admittance_matrix,
                admittance_matrix_21,
                node_index_2,
                node_index_1
            )
            insert_sub_matrix(
                self.node_admittance_matrix,
                admittance_matrix_22,
                node_index_2,
                node_index_2
            )

            # Add line element matrices to the branch admittance matrices.
            insert_sub_matrix(
                self.branch_admittance_1_matrix,
                admittance_matrix_11,
                branch_index,
                node_index_1
            )
            insert_sub_matrix(
                self.branch_admittance_1_matrix,
                admittance_matrix_12,
                branch_index,
                node_index_2
            )
            insert_sub_matrix(
                self.branch_admittance_2_matrix,
                admittance_matrix_21,
                branch_index,
                node_index_1
            )
            insert_sub_matrix(
                self.branch_admittance_2_matrix,
                admittance_matrix_22,
                branch_index,
                node_index_2
            )

            # Add line element matrices to the branch incidence matrices.
            insert_sub_matrix(
                self.branch_incidence_1_matrix,
                np.identity(len(branch_index), dtype=np.int),
                branch_index,
                node_index_1
            )
            insert_sub_matrix(
                self.branch_incidence_2_matrix,
                np.identity(len(branch_index), dtype=np.int),
                branch_index,
                node_index_2
            )
