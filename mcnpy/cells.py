import mcnpy
from mcnpy.numbered_object_collection import NumberedObjectCollection
from mcnpy.errors import MalformedInputError


class Cells(NumberedObjectCollection):
    """A collections of multiple :class:`mcnpy.cell.Cell` objects.

    :param cells: the list of cells to start with if needed
    :type cells: list
    :param problem: the problem to link this collection to.
    :type problem: MCNP_Problem
    """

    def __init__(self, cells=None, problem=None):
        super().__init__(mcnpy.Cell, cells, problem)

    def set_equal_importance(self, importance, vacuum_cells=tuple()):
        """
        Sets all cells except the vacuum cells to the same importance using :func:`mcnpy.data_cards.importance.Importance.all`.

        The vacuum cells will be set to 0.0. You can specify cell numbers or cell objects.

        :param importance: the importance to apply to all cells
        :type importance: float
        :param vacuum_cells: the cells that are the vacuum boundary with 0 importance
        :type vacuum_cells: list
        """
        if not isinstance(vacuum_cells, (list, tuple, set)):
            raise TypeError("vacuum_cells must be a list or set")
        cells_buff = set()
        for cell in vacuum_cells:
            if not isinstance(cell, (mcnpy.Cell, int)):
                raise TypeError("vacuum cell must be a Cell or a cell number")
            if isinstance(cell, int):
                cells_buff.add(self[cell])
            else:
                cells_buff.add(cell)
        vacuum_cells = cells_buff
        for cell in self:
            if cell not in vacuum_cells:
                cell.importance.all = importance
        for cell in vacuum_cells:
            cell.importance.all = 0.0

    @property
    def allow_mcnp_volume_calc(self):
        """
        Whether or not MCNP is allowed to automatically calculate cell volumes.

        :returns: true if MCNP will attempt to calculate cell volumes
        :rtype: bool
        """
        return self._volume.is_mcnp_calculated

    @allow_mcnp_volume_calc.setter
    def allow_mcnp_volume_calc(self, value):
        if not isinstance(value, bool):
            raise TypeError("allow_mcnp_volume_calc must be set to a bool")
        self._volume.is_mcnp_calculated = value

    def update_pointers(self, cells, materials, surfaces, data_inputs, problem):
        inputs_to_property = mcnpy.Cell._INPUTS_TO_PROPERTY
        inputs_to_always_update = {"_universe", "_fill"}
        inputs_loaded = set()
        # make a copy of the list
        for input in list(data_inputs):
            if type(input) in inputs_to_property:
                input_class = type(input)
                attr, cant_repeat = inputs_to_property[input_class]
                if cant_repeat and input_class in inputs_loaded:
                    raise MalformedInputError(
                        input,
                        f"The input: {type(input)} is only allowed once in a problem",
                    )
                if not hasattr(self, attr):
                    setattr(self, attr, input)
                    problem.print_in_data_block[input._class_prefix] = True
                else:
                    getattr(self, attr).merge(input)
                    data_inputs.remove(input)
                if cant_repeat:
                    inputs_loaded.add(type(input))
        for cell in self:
            cell.update_pointers(cells, materials, surfaces)
        for attr, _ in inputs_to_property.values():
            prop = getattr(self, attr, None)
            if prop is None:
                continue
            prop.push_to_cells()
            prop._clear_data()
        for input_class, (attr, _) in inputs_to_property.items():
            if not hasattr(self, attr):
                input = input_class()
                if attr in inputs_to_always_update:
                    input.push_to_cells()
                input._mutated = False
                input.link_to_problem(problem)
                setattr(self, attr, input)

    def _run_children_format_for_mcnp(self, data_inputs, mcnp_version):
        ret = []
        for attr, _ in mcnpy.Cell._INPUTS_TO_PROPERTY.values():
            if getattr(self, attr) not in data_inputs:
                ret += getattr(self, attr).format_for_mcnp_input(mcnp_version)
        return ret
