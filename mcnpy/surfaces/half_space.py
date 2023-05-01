import mcnpy
from mcnpy.errors import *
from mcnpy.geometry_operators import Operator
from mcnpy.input_parser.syntax_node import GeometryTree, ValueNode
from mcnpy.utilities import *


class HalfSpace:
    def __init__(self, left, operator, right=None, node=None):
        # TODO type enforcement
        self._left = left
        self._operator = operator
        self._right = right
        self._node = node
        self._cell = None

    @make_prop_pointer("_left", ())
    def left(self):
        pass

    @make_prop_pointer("_right", (), deletable=True)
    def right(self):
        pass

    @make_prop_pointer("_operator", Operator)
    def operator(self):
        pass

    @make_prop_pointer("_node")
    def node(self):
        pass

    @staticmethod
    def parse_input_node(node):
        sides = []
        for side in (node.left, node.right):
            if side is None:
                continue
            if isinstance(side, ValueNode):
                is_cell = node.operator == Operator.COMPLEMENT
                sides.append(UnitHalfSpace.parse_input_node(side, is_cell))
            else:
                sides.append(HalfSpace.parse_input_node(side))
        # ignore shifts, and simplify the tree
        if node.operator == Operator.SHIFT:
            return sides[0]
        if len(sides) == 1:
            sides.append(None)
        return HalfSpace(sides[0], node.operator, sides[1], node)

    def update_pointers(self, cells, surfaces, cell):
        self._cell = cell
        self.left.update_pointers(cells, surfaces, cell)
        if self.right is not None:
            self.right.update_pointers(cells, surfaces, cell)

    def _add_new_children_to_cell(self, other):
        cells, surfaces = other._get_leaf_objects()
        for container, parent in zip(
            (cells, surfaces), (self._cell.complements, self._cell.surfaces)
        ):
            for item in container:
                if item not in parent:
                    parent.append(item)

    def _get_leaf_objects(self):
        cells, surfaces = self.left._get_leaf_objects()
        if self.right:
            new_cells, new_surfaces = self.right._get_leaf_objects()
            cells |= new_cells
            surfaces |= new_surfaces
        return cells, surfaces

    def _update_values(self):
        self._update_operator()
        self.left._update_values()
        if self.right:
            self.right._update_values()

    def _update_operator(self):
        if self.node is None:
            self._generate_default_tree()
        operator_node = self.node.nodes["operator"]
        output = operator_node.format()
        if self.operator == Operator.INTERSECTION:
            if not output.isspace():
                self.__switch_operator(" ")
        elif self.operator == Operator.UNION:
            if ":" not in output:
                self.__switch_operator(":")
        elif self.operator == Operator.COMPLEMENT:
            if "#" not in output:
                self.__switch_operator("#")

    def __switch_operator(self, new_symbol):
        operator_node = self.node.nodes["operator"]
        operator_node._nodes = [
            n.replace("#", " ").replace(":", " ") for n in operator_node.nodes
        ]
        if new_symbol == "#":
            operator_node._nodes[-1] = operator_node.nodes[-1][:-1] + "#"
        elif new_symbol == ":":
            output = operator_node.format()
            midpoint = len(output) // 2
        total_len = 0
        for i, node in enumerate(operator_node.nodes):
            if total_len + len(node) >= midpoint:
                break
            total_len += len(node)
        index = midpoint - total_len
        operator_node._nodes[i] = node[:index] + ":" + node[index + 1 :]

    def __iand__(self, other):
        if not isinstance(other, HalfSpace):
            raise TypeError(f"Right hand side must be HalfSpace. {other} given.")
        left_leaf = isinstance(self.left, UnitHalfSpace)
        right_leaf = (
            self.right is not None and isinstance(self.right, UnitHalfSpace)
        ) or self.right is None
        if left_leaf and right_leaf:
            if self.right is not None:
                self.right = self.right & other
                return self
            else:
                return (~self.left) & other
        self.right &= other
        self._add_new_children_to_parent(other)
        return self

    def __ior__(self, other):
        if not isinstance(other, HalfSpace):
            raise TypeError(f"Right hand side must be HalfSpace. {other} given.")
        left_leaf = isinstance(self.left, UnitHalfSpace)
        right_leaf = (
            self.right is not None and isinstance(self.right, UnitHalfSpace)
        ) or self.right is None
        if left_leaf and right_leaf:
            if self.right is not None:
                self.right = self.right | other
                return self
            else:
                return (~self.left) | other
        self.right |= other
        self._add_new_children_to_parent(other)
        return sel

    def __and__(self, other):
        if not isinstance(other, HalfSpace):
            raise TypeError(f"Right hand side must be HalfSpace. {other} given.")
        return HalfSpace(self, Operator.INTERSECTION, other)

    def __or__(self, other):
        if not isinstance(other, HalfSpace):
            raise TypeError(f"Right hand side must be HalfSpace. {other} given.")
        return HalfSpace(self, Operator.UNION, other)

    def __invert__(self):
        if not isinstance(other, HalfSpace):
            raise TypeError(f"Right hand side must be HalfSpace. {other} given.")
        return HalfSpace(self, Operator.COMPLEMENT)

    def _generate_default_tree(self):
        pass


class UnitHalfSpace:
    def __init__(self, divider, side, is_cell, node=None):
        # TODO type enforcement
        self._divider = divider
        self._side = side
        self._is_cell = is_cell
        self._node = node
        self._cell = None

    @property
    def divider(self):
        """"""
        return self._divider

    # done manually to avoid circular imports
    @divider.setter
    def divider(self, div):
        if not isinstance(div, (mcnpy.Cell, Surface)):
            raise TypeError("Divider must be a Cell or Surface")
        self._divider = div

    @property
    def is_cell(self):
        return self._is_cell

    @property
    def node(self):
        return self._node

    @make_prop_pointer("_side", bool)
    def side(self):
        return self._side

    @staticmethod
    def parse_input_node(node, is_cell=False):
        if not isinstance(node, ValueNode):
            raise TypeError(f"Must be called on a ValueNode. {node} given.")
        node.is_negatable_identifier = True
        if is_cell:
            side = True
        else:
            side = not node.is_negative
        return UnitHalfSpace(node.value, side, is_cell, node)

    def update_pointers(self, cells, surfaces, cell):
        self._cell = cell
        container = surfaces
        if self._is_cell:
            container = cells
        try:
            self._divider = container[self._divider]
        except KeyError:
            if self._is_cell:
                raise BrokenObjectLinkError(
                    "Cell", self._cell.number, "Complement", self._divider
                )
            raise BrokenObjectLinkError(
                "Cell", self._cell.number, "Surface", self._divider
            )

    def _update_values(self):
        self._node.value = self.divider.number
        self._node.is_negative = self.side

    def _get_leaf_objects(self):
        if self._is_cell:
            return ({self._divider}, set())
        return (set(), {self._divider})
