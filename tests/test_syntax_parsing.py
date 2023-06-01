import copy
from io import StringIO
from unittest import TestCase

import mcnpy
from mcnpy.input_parser import input_syntax_reader
from mcnpy.input_parser.mcnp_input import Input, Jump, Message, ReadInput, Title
from mcnpy.input_parser.block_type import BlockType
from mcnpy.input_parser.parser_base import MCNP_Parser
from mcnpy.input_parser import syntax_node
from mcnpy.particle import Particle


class TestValueNode(TestCase):
    def test_valuenoode_init(self):
        for type, token, answer in [
            (str, "hi", "hi"),
            (float, "1.2300", 1.23),
            (int, "1", 1),
            (float, "1.23e-3", 1.23e-3),
            (float, "6.02+23", 6.02e23),
        ]:
            for padding in [None, syntax_node.PaddingNode(" ")]:
                node = syntax_node.ValueNode(token, type, padding)
                self.assertEqual(node.value, answer)
                self.assertEqual(node.token, token)
                if padding:
                    self.assertEqual(node.padding, padding)
                else:
                    self.assertIsNone(node.padding)
        # test with None values
        for type in {str, float, int}:
            node = syntax_node.ValueNode(None, type)
            self.assertIsNone(node.value)
            node = syntax_node.ValueNode(Jump(), type)
            self.assertIsNone(node.value)

    def test_valuenode_convert_to_int(self):
        node = syntax_node.ValueNode("1", float)
        node._convert_to_int()
        self.assertEqual(node.type, int)
        self.assertEqual(node.value, 1)
        # test 1.0
        node = syntax_node.ValueNode("1.0", float)
        node._convert_to_int()
        self.assertEqual(node.type, int)
        self.assertEqual(node.value, 1)
        # test wrong type
        with self.assertRaises(ValueError):
            node = syntax_node.ValueNode("hi", str)
            node._convert_to_int()
        # test real float
        with self.assertRaises(ValueError):
            node = syntax_node.ValueNode("1.23", float)
            node._convert_to_int()

    def test_valuenode_convert_to_enum(self):
        node = syntax_node.ValueNode("1", float)
        lat = mcnpy.data_inputs.lattice.Lattice
        node._convert_to_enum(lat)
        self.assertEqual(node.type, lat)
        self.assertEqual(node.value, lat(1))
        # test with None
        with self.assertRaises(ValueError):
            node = syntax_node.ValueNode(None, float)
            node._convert_to_enum(lat)
        node._convert_to_enum(lat, allow_none=True)
        self.assertIsNone(node.value)
        st = mcnpy.surfaces.surface_type.SurfaceType
        node = syntax_node.ValueNode("p", str)
        node._convert_to_enum(st, switch_to_upper=True)
        self.assertEqual(node.type, st)
        self.assertEqual(node.value, st("P"))

    def test_is_negat_identifier(self):
        node = syntax_node.ValueNode("-1", float)
        self.assertTrue(not node.is_negatable_identifier)
        self.assertIsNone(node.is_negative)
        node.is_negatable_identifier = True
        self.assertTrue(node.is_negatable_identifier)
        self.assertEqual(node.type, int)
        self.assertTrue(node.value > 0)
        self.assertTrue(node.is_negative)
        # test with positive number
        node = syntax_node.ValueNode("1", float)
        node.is_negatable_identifier = True
        self.assertEqual(node.type, int)
        self.assertTrue(node.value > 0)
        self.assertTrue(not node.is_negative)
        # test with none
        node = syntax_node.ValueNode(None, float)
        node.is_negatable_identifier = True
        self.assertEqual(node.type, int)
        self.assertIsNone(node.value)
        self.assertIsNone(node.is_negative)
        node.value = 1
        self.assertEqual(node.value, 1)
        self.assertTrue(not node.is_negative)

    def test_is_negat_float(self):
        node = syntax_node.ValueNode("-1.23", float)
        self.assertTrue(not node.is_negatable_float)
        self.assertIsNone(node.is_negative)
        node.is_negatable_float = True
        self.assertEqual(node.type, float)
        self.assertTrue(node.value > 0)
        self.assertTrue(node.is_negative)
        self.assertTrue(node.is_negatable_float)
        # test with positive number
        node = syntax_node.ValueNode("1.23", float)
        node.is_negatable_float = True
        self.assertEqual(node.type, float)
        self.assertTrue(not node.is_negative)
        # test with None
        node = syntax_node.ValueNode(None, float)
        node.is_negatable_float = True
        self.assertEqual(node.type, float)
        self.assertIsNone(node.value)
        self.assertIsNone(node.is_negative)
        node.value = 1
        self.assertEqual(node.value, 1)
        self.assertTrue(not node.is_negative)

    def test_is_negative(self):
        node = syntax_node.ValueNode("-1.23", float)
        node.is_negatable_float = True
        self.assertTrue(node.is_negative)
        node.is_negative = False
        self.assertTrue(node.value > 0)
        self.assertTrue(not node.is_negative)
        node = syntax_node.ValueNode("hi", str)
        node.is_negative = True
        self.assertIsNone(node.is_negative)

    def test_valuenode_int_format(self):
        node = syntax_node.ValueNode("-1", int)
        answer = "-1"
        output = node.format()
        self.assertEqual(output, answer)
        for input, val, answer in [
            ("1", 5, "5"),
            ("-1", 2, " 2"),
            ("-1", -2, "-2"),
            ("+1", 5, "+5"),
            ("0001", 5, "0005"),
            (Jump(), 5, "5"),
        ]:
            node = syntax_node.ValueNode(input, int)
            node.value = val
            self.assertEqual(node.format(), answer)
            node = syntax_node.ValueNode(input, int)
            node.is_negatable_identifier = True
            node.value = val
            node.is_negative = val < 0
            self.assertEqual(node.format(), answer)
        # test messing around with padding
        for padding, val, answer in [
            ([" "], 10, "10 "),
            (["  "], 10, "10 "),
            (["\n"], 10, "10\n"),
            ([" ", "\n", "c hi"], 10, "10\nc hi"),
            ([" ", " "], 10, "10 "),
        ]:
            pad_node = syntax_node.PaddingNode(padding[0])
            for pad in padding[1:]:
                pad_node.append(pad)
            node = syntax_node.ValueNode("1", int, pad_node)
            node.value = val
            self.assertEqual(node.format(), answer)

    def test_value_has_changed(self):
        # test None no change
        node = syntax_node.ValueNode(None, int)
        self.assertTrue(not node._value_changed)
        # test None changed
        node.value = 5
        self.assertTrue(node._value_changed)
        node = syntax_node.ValueNode("1.23", float)
        self.assertTrue(not node._value_changed)
        node.value = 1.25
        self.assertTrue(node._value_changed)
        node = syntax_node.ValueNode("hi", str)
        self.assertTrue(not node._value_changed)
        node.value = "foo"
        self.assertTrue(node._value_changed)

    def test_value_float_format(self):
        for input, val, answer in [
            ("1.23", 1.23, "1.23"),
            ("1.23", 4.56, "4.56"),
            ("-1.23", 4.56, " 4.56"),
            ("1.0e-2", 2, "2.0e+0"),
            ("1.602-19", 6.02e23, "6.020+23"),
            ("1.602-0019", 6.02e23, "6.020+0023"),
            (Jump(), 5.4, "5.4"),
            ("1", 2, "2"),
            ("0.5", 0, "0.0"),
        ]:
            node = syntax_node.ValueNode(input, float)
            node.value = val
            self.assertEqual(node.format(), answer)
        for padding, val, answer in [
            ([" "], 10, "10.0 "),
            (["  "], 10, "10.0 "),
            (["\n"], 10, "10.0\n"),
            ([" ", "\n", "c hi"], 10, "10.0\nc hi"),
            ([" ", " "], 10, "10.0 "),
        ]:
            pad_node = syntax_node.PaddingNode(padding[0])
            for pad in padding[1:]:
                pad_node.append(pad)
            node = syntax_node.ValueNode("1.0", float, pad_node)
            node.value = val
            self.assertEqual(node.format(), answer)

    def test_value_str_format(self):
        for input, val, answer in [
            ("hi", "foo", "foo"),
            ("hi", None, ""),
        ]:
            node = syntax_node.ValueNode(input, str)
            node.value = val
            self.assertEqual(node.format(), answer)
        for padding, val, answer in [
            ([" "], "foo", "foo "),
            (["  "], "foo", "foo "),
            (["\n"], "foo", "foo\n"),
            ([" ", "\n", "c hi"], "foo", "foo\nc hi"),
            ([" ", " "], "foo", "foo "),
        ]:
            pad_node = syntax_node.PaddingNode(padding[0])
            for pad in padding[1:]:
                pad_node.append(pad)
            node = syntax_node.ValueNode("hi", str, pad_node)
            node.value = val
            self.assertEqual(node.format(), answer)

    def test_value_enum_format(self):
        lat = mcnpy.data_inputs.lattice.Lattice
        st = mcnpy.surfaces.surface_type.SurfaceType
        for input, val, enum_class, args, answer in [
            (
                "1",
                lat.HEXAGONAL,
                lat,
                {"format_type": int, "switch_to_upper": False},
                "2",
            ),
            ("p", st.PZ, st, {"format_type": str, "switch_to_upper": True}, "PZ"),
        ]:
            node = syntax_node.ValueNode(input, args["format_type"])
            node._convert_to_enum(enum_class, **args)
            node.value = val
            self.assertEqual(node.format(), answer)

    def test_value_comments(self):
        value_node = syntax_node.ValueNode("1", int)
        self.assertEqual(len(list(value_node.comments)), 0)
        padding = syntax_node.PaddingNode("$ hi", True)
        value_node.padding = padding
        comments = list(value_node.comments)
        self.assertEqual(len(comments), 1)
        self.assertIn("hi", comments[0].contents)

    def test_value_trailing_comments(self):
        value_node = syntax_node.ValueNode("1", int)
        self.assertIsNone(value_node.get_trailing_comment())
        value_node._delete_trailing_comment()
        self.assertIsNone(value_node.get_trailing_comment())
        padding = syntax_node.PaddingNode("$ hi", True)
        value_node.padding = padding
        comment = value_node.get_trailing_comment()
        self.assertEqual(len(comment), 1)
        self.assertEqual(comment[0].contents, "hi")
        value_node._delete_trailing_comment()
        self.assertIsNone(value_node.get_trailing_comment())

    def test_value_str(self):
        value_node = syntax_node.ValueNode("1", int)
        str(value_node)
        repr(value_node)
        padding = syntax_node.PaddingNode("$ hi", True)
        value_node.padding = padding
        str(value_node)
        repr(value_node)

    def test_value_equality(self):
        value_node1 = syntax_node.ValueNode("1", int)
        self.assertTrue(value_node1 == value_node1)
        with self.assertRaises(TypeError):
            value_node1 == syntax_node.PaddingNode("")
        value_node2 = syntax_node.ValueNode("2", int)
        self.assertTrue(value_node1 != value_node2)
        value_node3 = syntax_node.ValueNode("hi", str)
        self.assertTrue(value_node1 != value_node3)
        self.assertTrue(value_node1 == 1)
        self.assertTrue(value_node1 != 2)
        self.assertTrue(value_node1 != "hi")
        value_node4 = syntax_node.ValueNode("1.5", float)
        value_node5 = syntax_node.ValueNode("1.50000000000001", float)
        self.assertTrue(value_node4 == value_node5)
        value_node5.value = 2.0
        self.assertTrue(value_node4 != value_node5)


class TestSyntaxNode(TestCase):
    def setUp(self):
        value1 = syntax_node.ValueNode("1.5", float)
        value2 = syntax_node.ValueNode("1", int)
        self.test_node = syntax_node.SyntaxNode(
            "test",
            {"foo": value1, "bar": value2, "bar2": syntax_node.SyntaxNode("test2", {})},
        )

    def test_syntax_init(self):
        test = self.test_node
        self.assertEqual(test.name, "test")
        self.assertIn("foo", test.nodes)
        self.assertIn("bar", test.nodes)
        self.assertIsInstance(test.nodes["foo"], syntax_node.ValueNode)

    def test_syntax_name(self):
        test = self.test_node
        test.name = "hi"
        self.assertEqual(test.name, "hi")
        with self.assertRaises(TypeError):
            test.name = 1.0

    def test_get_value(self):
        test = self.test_node
        self.assertEqual(test.get_value("foo"), 1.5)
        with self.assertRaises(KeyError):
            test.get_value("foo2")
        with self.assertRaises(KeyError):
            test.get_value("bar2")

    def test_syntax_format(self):
        output = self.test_node.format()
        self.assertEqual(output, "1.51")

    def test_syntax_dict(self):
        test = self.test_node
        self.assertIn("foo", test)
        self.assertEqual(test["foo"], test.nodes["foo"])

    def test_syntax_comments(self):
        padding = syntax_node.PaddingNode("$ hi", True)
        test = copy.deepcopy(self.test_node)
        test["foo"].padding = padding
        padding = syntax_node.PaddingNode("$ foo", True)
        test["bar"].padding = padding
        comments = list(test.comments)
        self.assertEqual(len(comments), 2)

    def test_syntax_trailing_comments(self):
        # test with blank tail
        self.assertIsNone(self.test_node.get_trailing_comment())
        test = copy.deepcopy(self.test_node)
        test["bar2"].nodes["foo"] = syntax_node.ValueNode("1.23", float)
        self.assertIsNone(test.get_trailing_comment())
        test["bar2"]["foo"].padding = syntax_node.PaddingNode("$ hi", True)
        self.assertEqual(len(test.get_trailing_comment()), 1)
        test._delete_trailing_comment()
        self.assertIsNone(test.get_trailing_comment())

    def test_syntax_str(self):
        str(self.test_node)
        repr(self.test_node)


class TestGeometryTree(TestCase):
    def setUp(self):
        left = syntax_node.ValueNode("1", int)
        right = syntax_node.ValueNode("2", int)
        op = syntax_node.PaddingNode(" ")
        self.test_tree = syntax_node.GeometryTree(
            "test",
            {"left": left, "operator": op, "right": right},
            mcnpy.Operator.INTERSECTION,
            left,
            right,
        )

    def test_geometry_init(self):
        left = syntax_node.ValueNode("1", int)
        right = syntax_node.ValueNode("2", int)
        op = syntax_node.PaddingNode(" ")
        tree = syntax_node.GeometryTree(
            "test",
            {"left": left, "operator": op, "right": right},
            mcnpy.Operator.INTERSECTION,
            left,
            right,
        )
        self.assertIs(tree.left, left)
        self.assertIs(tree.right, right)
        self.assertEqual(tree.operator, mcnpy.Operator.INTERSECTION)

    def test_geometry_format(self):
        test = self.test_tree
        self.assertEqual(test.format(), "1 2")

    def test_geometry_str(self):
        test = self.test_tree
        str(test)
        repr(test)

    def test_geometry_comments(self):
        test = copy.deepcopy(self.test_tree)
        test.left.padding = syntax_node.PaddingNode("$ hi", True)
        comments = list(test.comments)
        self.assertEqual(len(comments), 1)


class TestPaddingNode(TestCase):
    def test_padding_init(self):
        pad = syntax_node.PaddingNode(" ")
        self.assertEqual(len(pad.nodes), 1)
        self.assertEqual(pad.value, " ")

    def test_padding_is_space(self):
        pad = syntax_node.PaddingNode(" ")
        self.assertTrue(pad.is_space(0))
        pad.append("\n")
        self.assertTrue(not pad.is_space(1))
        pad.append("$ hi", True)
        self.assertTrue(not pad.is_space(2))
        with self.assertRaises(IndexError):
            pad.is_space(5)

    def test_padding_append(self):
        pad = syntax_node.PaddingNode(" ")
        pad.append("\n")
        self.assertEqual(len(pad), 2)
        pad.append(" ")
        self.assertEqual(len(pad), 3)
        pad.append(" \n")
        self.assertEqual(len(pad), 5)
        pad.append("$ hi", True)
        self.assertEqual(len(pad), 6)

    def test_padding_format(self):
        pad = syntax_node.PaddingNode(" ")
        self.assertEqual(pad.format(), " ")
        pad.append("$ hi", True)
        self.assertEqual(pad.format(), " $ hi")

    def test_padding_grab_beginning_format(self):
        pad = syntax_node.PaddingNode(" ")
        new_pad = [
            syntax_node.CommentNode("c hi"),
            "\n",
            syntax_node.CommentNode("c foo"),
        ]
        answer = copy.copy(new_pad)
        pad._grab_beginning_comment(new_pad)
        self.assertEqual(pad.nodes, answer + ["\n", " "])

    def test_padding_eq(self):
        pad = syntax_node.PaddingNode(" ")
        self.assertTrue(pad == " ")
        self.assertTrue(pad != " hi ")
        pad1 = syntax_node.PaddingNode(" ")
        self.assertTrue(pad == pad1)
        with self.assertRaises(TypeError):
            pad == 1

    def test_comment_init(self):
        comment = syntax_node.CommentNode("$ hi")
        self.assertIsInstance(comment.nodes[0], syntax_node.SyntaxNode)
        self.assertEqual(len(comment.nodes), 1)
        self.assertTrue(comment.is_dollar)
        comment = syntax_node.CommentNode(" c hi")
        self.assertTrue(not comment.is_dollar)
        self.assertEqual(len(list(comment.comments)), 1)

    def test_comment_append(self):
        comment = syntax_node.CommentNode("c foo")
        comment.append("c bar")
        self.assertEqual(len(comment.nodes), 2)
        # test mismatch
        comment = syntax_node.CommentNode("$ hi")
        with self.assertRaises(TypeError):
            comment.append("c hi")

    def test_comment_str(self):
        comment = syntax_node.CommentNode("$ hi")
        str(comment)
        repr(comment)


class TestParticlesNode(TestCase):
    def test_particle_init(self):
        parts = syntax_node.ParticleNode("test", ":n,p,e")
        particle = mcnpy.particle.Particle
        answers = {particle.NEUTRON, particle.PHOTON, particle.ELECTRON}
        self.assertEqual(parts.particles, answers)
        self.assertEqual(len(list(parts.comments)), 0)
        for part in parts:
            self.assertIn(part, answers)
        answers = [particle.NEUTRON, particle.PHOTON, particle.ELECTRON]
        self.assertEqual(parts._particles_sorted, answers)

    def test_particles_setter(self):
        parts = syntax_node.ParticleNode("test", "n,p,e")
        particle = mcnpy.particle.Particle
        parts.particles = {particle.TRITON}
        self.assertEqual(parts.particles, {particle.TRITON})
        parts.particles = [particle.TRITON]
        self.assertEqual(parts.particles, {particle.TRITON})
        with self.assertRaises(TypeError):
            parts.particles = "hi"
        with self.assertRaises(TypeError):
            parts.particles = {"hi"}

    def test_particles_add_remove(self):
        parts = syntax_node.ParticleNode("test", "n,p,e")
        particle = mcnpy.particle.Particle
        parts.add(particle.TRITON)
        self.assertIn(particle.TRITON, parts)
        self.assertEqual(parts._particles_sorted[-1], particle.TRITON)
        with self.assertRaises(TypeError):
            parts.add("hi")
        parts.remove(particle.NEUTRON)
        self.assertNotIn(particle.NEUTRON, parts)
        with self.assertRaises(TypeError):
            parts.remove("hi")

    def test_particles_sorted(self):
        parts = syntax_node.ParticleNode("test", "n,p,e")
        particle = mcnpy.particle.Particle
        # lazily work around internals
        parts._particles.remove(particle.NEUTRON)
        self.assertNotIn(particle.NEUTRON, parts._particles_sorted)
        parts._particles.add(particle.TRITON)
        self.assertIn(particle.TRITON, parts._particles_sorted)

    def test_particles_format(self):
        parts = syntax_node.ParticleNode("test", "n,p,e")
        repr(parts)
        self.assertEqual(parts.format(), ":n,p,e")
        parts = syntax_node.ParticleNode("test", "N,P,E")
        self.assertEqual(parts.format(), ":N,P,E")


class TestListNode(TestCase):
    def test_list_init(self):
        list_node = syntax_node.ListNode("list")
        self.assertEqual(list_node.nodes, [])

    def test_list_append(self):
        list_node = syntax_node.ListNode("list")
        list_node.append(syntax_node.ValueNode("1.0", float))
        self.assertEqual(len(list_node), 1)

    def test_list_slicing(self):
        list_node = syntax_node.ListNode("list")
        for i in range(20):
            list_node.append(syntax_node.ValueNode("1.0", float))
        self.assertEqual(list_node[5], syntax_node.ValueNode("1.0", float))
        for val in list_node[1:5]:
            self.assertEqual(val, syntax_node.ValueNode("1.0", float))
        for val in list_node[1:5:1]:
            self.assertEqual(val, syntax_node.ValueNode("1.0", float))
        for val in list_node[::1]:
            self.assertEqual(val, syntax_node.ValueNode("1.0", float))
        for val in list_node[5:1:-1]:
            self.assertEqual(val, syntax_node.ValueNode("1.0", float))
        for val in list_node[::-1]:
            self.assertEqual(val, syntax_node.ValueNode("1.0", float))
        with self.assertRaises(IndexError):
            list_node[50]

    def test_list_equality(self):
        list_node1 = syntax_node.ListNode("list")
        for i in range(20):
            list_node1.append(syntax_node.ValueNode("1.0", float))
        with self.assertRaises(TypeError):
            list_node1 == "hi"
        list2 = [syntax_node.ValueNode("1.0", float)] * 19
        self.assertTrue(not list_node1 == list2)
        list2 = [syntax_node.ValueNode("1.0", float)] * 20
        self.assertTrue(list_node1 == list2)
        list2 = [syntax_node.ValueNode("1.0", float)] * 19 + [
            syntax_node.ValueNode("1.5", float)
        ]
        self.assertTrue(list_node1 != list2)

    def test_list_trailing_comment(self):
        list_node1 = syntax_node.ListNode("list")
        for i in range(20):
            list_node1.append(syntax_node.ValueNode("1.0", float))
        padding = syntax_node.PaddingNode("$ hi", True)
        list_node1[-1].padding = padding
        comments = list(list_node1.get_trailing_comment())
        self.assertEqual(len(comments), 1)
        list_node1._delete_trailing_comment()
        self.assertIsNone(list_node1.get_trailing_comment())
        # test an empty list
        list_node1 = syntax_node.ListNode("list")
        self.assertIsNone(list_node1.get_trailing_comment())
        list_node1._delete_trailing_comment()
        self.assertIsNone(list_node1.get_trailing_comment())

    def test_list_format(self):
        list_node = syntax_node.ListNode("list")
        for i in range(20):
            list_node.append(syntax_node.ValueNode("1.0", float))
        self.assertEqual(list_node.format(), "1.0 " * 19 + "1.0")

    def test_list_comments(self):
        list_node = syntax_node.ListNode("list")
        for i in range(20):
            list_node.append(syntax_node.ValueNode("1.0", float))
        padding = syntax_node.PaddingNode("$ hi", True)
        list_node[-1].padding = padding
        comments = list(list_node.comments)
        self.assertEqual(len(comments), 1)


class TestIsotopesNode(TestCase):
    def test_isotopes_init(self):
        isotope = syntax_node.IsotopesNode("test")
        self.assertEqual(isotope.name, "test")
        self.assertIsInstance(isotope.nodes, list)

    def test_isotopes_append(self):
        isotopes = syntax_node.IsotopesNode("test")
        zaid = syntax_node.ValueNode("1001.80c", str)
        concentration = syntax_node.ValueNode("1.5", float)
        isotopes.append(("isotope_fraction", zaid, concentration))
        self.assertEqual(isotopes.nodes[-1][0], zaid)
        self.assertEqual(isotopes.nodes[-1][1], concentration)

    def test_isotopes_format(self):
        padding = syntax_node.PaddingNode(" ")
        isotopes = syntax_node.IsotopesNode("test")
        zaid = syntax_node.ValueNode("1001.80c", str)
        zaid.padding = padding
        concentration = syntax_node.ValueNode("1.5", float)
        concentration.padding = padding
        isotopes.append(("isotope_fraction", zaid, concentration))
        self.assertEqual(isotopes.format(), "1001.80c 1.5 ")

    def test_isotopes_str(self):
        isotopes = syntax_node.IsotopesNode("test")
        zaid = syntax_node.ValueNode("1001.80c", str)
        concentration = syntax_node.ValueNode("1.5", float)
        isotopes.append(("isotope_fraction", zaid, concentration))
        str(isotopes)
        repr(isotopes)

    def test_isotopes_iter(self):
        isotopes = syntax_node.IsotopesNode("test")
        zaid = syntax_node.ValueNode("1001.80c", str)
        concentration = syntax_node.ValueNode("1.5", float)
        isotopes.append(("isotope_fraction", zaid, concentration))
        isotopes.append(("isotope_fraction", zaid, concentration))
        for combo in isotopes:
            self.assertEqual(len(combo), 2)

    def test_isotopes_comments(self):
        padding = syntax_node.PaddingNode(" ")
        isotopes = syntax_node.IsotopesNode("test")
        zaid = syntax_node.ValueNode("1001.80c", str)
        zaid.padding = padding
        concentration = syntax_node.ValueNode("1.5", float)
        padding = copy.deepcopy(padding)
        padding.append("$ hi", True)
        concentration.padding = padding
        isotopes.append(("isotope_fraction", zaid, concentration))
        comments = list(isotopes.comments)
        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0].contents, "hi")

    def test_isotopes_trailing_comment(self):
        padding = syntax_node.PaddingNode(" ")
        isotopes = syntax_node.IsotopesNode("test")
        zaid = syntax_node.ValueNode("1001.80c", str)
        zaid.padding = padding
        concentration = syntax_node.ValueNode("1.5", float)
        padding = copy.deepcopy(padding)
        padding.append("c hi", True)
        concentration.padding = padding
        isotopes.append(("isotope_fraction", zaid, concentration))
        comments = isotopes.get_trailing_comment()
        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0].contents, "hi")
        isotopes._delete_trailing_comment()
        comments = isotopes.get_trailing_comment()
        self.assertIsNone(comments)


class TestShortcutNode(TestCase):
    def test_basic_shortcut_init(self):
        with self.assertRaises(ValueError):
            syntax_node.ShortcutNode("")
        # test a blank init
        shortcut = syntax_node.ShortcutNode(
            short_type=syntax_node.Shortcuts.LOG_INTERPOLATE
        )
        self.assertEqual(shortcut._type, syntax_node.Shortcuts.LOG_INTERPOLATE)
        self.assertEqual(shortcut.end_padding.nodes, [" "])
        with self.assertRaises(TypeError):
            syntax_node.ShortcutNode(short_type="")

    def test_shortcut_end_padding_setter(self):
        short = syntax_node.ShortcutNode()
        pad = syntax_node.PaddingNode(" ")
        short.end_padding = pad
        self.assertEqual(short.end_padding, pad)
        with self.assertRaises(TypeError):
            short.end_padding = " "

    def test_shortcut_expansion(self):
        """
        Most examples, unless otherwise noted are taken from Section 2.8.1
        of LA-UR-17-29981.
        """
        tests = {
            "1 3M 2r": [1, 3, 3, 3],
            # unofficial
            "0.01 2ILOG 10": [0.01, 0.1, 1, 10],
            "1 3M I 4": [1, 3, 3.5, 4],
            "1 3M 3M": [1, 3, 9],
            "1 2R 2I 2.5": [1, 1, 1, 1.5, 2, 2.5],
            "1 R 2m": [1, 1, 2],
            "1 R R": [1, 1, 1],
            "1 2i 4 3m": [1, 2, 3, 4, 12],
            # unofficial
            "1 i 3": [1, 2, 3],
            # unofficial
            "1 ilog 100": [1, 10, 100],
            # last official one
            "1 2i 4 2i 10": [
                1,
                2,
                3,
                4,
                6,
                8,
                10,
            ],
            "1 2j 4": [1, mcnpy.Jump(), mcnpy.Jump(), 4],
            "1 j": [1, mcnpy.Jump()],
        }
        invalid = [
            "3J 4R",
            "1 4I 3M",
            # last official test
            "1 4I J",
            "1 2Ilog J",
            "J 2Ilog 5",
            "3J 2M",
            "10 M",
            "2R",
        ]

        parser = ShortcutTestFixture()
        for test, answer in tests.items():
            print(test)
            input = Input([test], BlockType.DATA)
            parsed = parser.parse(input.tokenize())
            for val, gold in zip(parsed, answer):
                if val.value is None:
                    self.assertEqual(gold, mcnpy.Jump())
                else:
                    self.assertAlmostEqual(val.value, gold)
        for test in invalid:
            print(test)
            with self.assertRaises(mcnpy.errors.MalformedInputError):
                input = Input([test], BlockType.DATA)
                parsed = parser.parse(input.tokenize())
                if parsed is None:
                    raise mcnpy.errors.MalformedInputError("", "")

    def test_shortcut_geometry_expansion(self):
        tests = {
            "1 3r ": [1, 1, 1, 1],
            "1 1 3r ": [1, 1, 1, 1, 1],
            "1 -2M ": [1, -2],
            "1 2i 4 ": [1, 2, 3, 4],
            "1 1 2i 4 ": [1, 1, 2, 3, 4],
            "1 ilog 100 ": [1, 10, 100],
            # secretly test iterator
            "#1": [1],
            "#(1 2 3)": [1, 2, 3],
            "1 2:( 3 4 5)": [1, 2, 3, 4, 5],
        }

        parser = ShortcutGeometryTestFixture()
        for test, answer in tests.items():
            print(test)
            input = Input([test], BlockType.CELL)
            parsed = parser.parse(input.tokenize())
            for val, gold in zip(parsed, answer):
                self.assertAlmostEqual(val.value, gold)


class ShortcutTestFixture(MCNP_Parser):
    @_("number_sequence", "shortcut_sequence")
    def shortcut_magic(self, p):
        return p[0]


class ShortcutGeometryTestFixture(mcnpy.input_parser.cell_parser.CellParser):
    @_("geometry_expr")
    def geometry(self, p):
        return p[0]


class TestShortcutListIntegration(TestCase):
    def setUp(self):
        self.parser = ShortcutTestFixture()
        input = Input(["1 1 2i 4"], BlockType.DATA)
        self.list_node = self.parser.parse(input.tokenize())

    def test_shortcut_list_node_init(self):
        answers = [1, 1, 2, 3, 4]
        for val, gold in zip(self.list_node, answers):
            self.assertAlmostEqual(val.value, gold)

    def test_shortcut_list_update_vals(self):
        list_node = copy.deepcopy(self.list_node)
        values = list(list_node)
        list_node.update_with_new_values(values)
        self.assertEqual(list(list_node), values)

    def test_shortcut_list_update_vals_repeat(self):
        input = Input(["1 2 3 5R 0 0"], BlockType.DATA)
        list_node = self.parser.parse(input.tokenize())
        values = list(list_node)
        values.insert(2, syntax_node.ValueNode(3.0, float))
        list_node.update_with_new_values(values)
        print(list_node.nodes)
        self.assertEqual(list(list_node), values)


class TestSyntaxParsing(TestCase):
    def testCardInit(self):
        with self.assertRaises(TypeError):
            Input("5", BlockType.CELL)
        with self.assertRaises(TypeError):
            Input([5], BlockType.CELL)
        with self.assertRaises(TypeError):
            Input(["5"], "5")

    def testMessageInit(self):
        with self.assertRaises(TypeError):
            Message(["hi"], "5")
        with self.assertRaises(TypeError):
            Message(["hi"], [5])

    def testTitleInit(self):
        with self.assertRaises(TypeError):
            Title(["hi"], 5)

    def testMessageFinder(self):
        test_message = "this is a message"
        test_string = f"""message: {test_message}

test title
"""
        for tester, validator in [
            (test_string, test_message),
            (test_string.upper(), test_message.upper()),
        ]:
            with StringIO(tester) as fh:
                generator = input_syntax_reader.read_front_matters(fh, (6, 2, 0))
                card = next(generator)
                self.assertIsInstance(card, mcnpy.input_parser.mcnp_input.Message)
                self.assertEqual(card.lines[0], validator)
                self.assertEqual(len(card.lines), 1)

    def testReadCardStr(self):
        card = ReadInput(["Read file=hi.imcnp"], BlockType.CELL)
        self.assertEqual(str(card), "READ INPUT: Block_Type: BlockType.CELL")
        self.assertEqual(
            repr(card),
            "READ INPUT: BlockType.CELL: ['Read file=hi.imcnp'] File: hi.imcnp",
        )

    def testTitleFinder(self):
        test_title = "Richard Stallman writes GNU"
        test_string = f"""{test_title}
1 0 -1
"""
        for tester, validator in [
            (test_string, test_title),
            (test_string.upper(), test_title.upper()),
        ]:
            with StringIO(tester) as fh:
                generator = input_syntax_reader.read_front_matters(fh, (6, 2, 0))
                card = next(generator)
                self.assertIsInstance(card, mcnpy.input_parser.mcnp_input.Title)
                self.assertEqual(card.title, validator)

    def testCardFinder(self):
        test_string = """1 0 -1
     5"""
        for i in range(5):
            tester = " " * i + test_string
            with StringIO(tester) as fh:
                generator = input_syntax_reader.read_data(fh, (6, 2, 0))
                card = next(generator)
                self.assertIsInstance(card, mcnpy.input_parser.mcnp_input.Input)
                answer = [" " * i + "1 0 -1", "     5"]
                self.assertEqual(len(answer), len(card.input_lines))
                for j, line in enumerate(card.input_lines):
                    self.assertEqual(line, answer[j])
                self.assertEqual(
                    card.block_type, mcnpy.input_parser.block_type.BlockType.CELL
                )

    # TODO ensure this is tested in Input parsers
    """
    def testCommentFinder(self):
        for i in range(5):
            tester = " " * i + test_string
            with StringIO(tester) as fh:
                card = next(input_syntax_reader.read_data(fh, (6, 2, 0)))
                self.assertIsInstance(card, mcnpy.input_parser.mcnp_input.Comment)
                self.assertEqual(len(card.lines), 5)
                self.assertEqual(card.lines[0], "foo")
                self.assertEqual(card.lines[1], "bar")
                self.assertEqual(card.lines[3], "bop")
    """

    def testReadCardFinder(self):
        test_string = "read file=foo.imcnp "
        with StringIO(test_string) as fh:
            card = next(input_syntax_reader.read_data(fh, (6, 2, 0)))
            self.assertIsNone(card)  # the read input is hidden from the user

    def testBlockId(self):
        test_string = "1 0 -1"
        for i in range(3):
            tester = "\n" * i + test_string
            with StringIO(tester) as fh:
                for card in input_syntax_reader.read_data(fh, (6, 2, 0)):
                    pass
                self.assertEqual(
                    mcnpy.input_parser.block_type.BlockType(i), card.block_type
                )

    def testCommentFormatInput(self):
        in_strs = ["c foo", "c bar"]
        card = mcnpy.input_parser.syntax_node.CommentNode(in_strs[0])
        output = card.format()
        answer = "c foo"
        str_answer = """COMMENT:
c foo"""
        self.assertEqual(repr(card), str_answer)
        self.assertEqual("c foo", str(card))
        self.assertEqual(len(answer), len(output))
        for i, line in enumerate(output):
            self.assertEqual(answer[i], line)

    def testMessageFormatInput(self):
        answer = ["MESSAGE: foo", "bar", ""]
        card = mcnpy.input_parser.mcnp_input.Message(answer, ["foo", "bar"])
        str_answer = """MESSAGE:
foo
bar
"""
        self.assertEqual(str_answer, repr(card))
        self.assertEqual("MESSAGE: 2 lines", str(card))
        output = card.format_for_mcnp_input((6, 2, 0))
        self.assertEqual(len(answer), len(output))
        for i, line in enumerate(output):
            self.assertEqual(answer[i], line)

    def testTitleFormatInput(self):
        card = mcnpy.input_parser.mcnp_input.Title(["foo"], "foo")
        answer = ["foo"]
        str_answer = "TITLE: foo"
        self.assertEqual(str(card), str_answer)
        output = card.format_for_mcnp_input((6, 2, 0))
        self.assertEqual(len(answer), len(output))
        for i, line in enumerate(output):
            self.assertEqual(answer[i], line)

    def testReadInput(self):
        # TODO ensure comments are properly glued to right input
        generator = input_syntax_reader.read_input_syntax("tests/inputs/test.imcnp")
        mcnp_in = mcnpy.input_parser.mcnp_input
        input_order = [mcnp_in.Message, mcnp_in.Title]
        input_order += [mcnp_in.Input] * 17
        for i, input in enumerate(generator):
            print(input.input_lines)
            print(input_order[i])
            self.assertIsInstance(input, input_order[i])

    def testReadInputWithRead(self):
        generator = input_syntax_reader.read_input_syntax("tests/inputs/testRead.imcnp")
        next(generator)  # skip title
        next(generator)  # skip read none
        card = next(generator)
        answer = ["1 0 -1"]
        self.assertEqual(answer, card.input_lines)

    def testReadInputWithVertMode(self):
        generator = input_syntax_reader.read_input_syntax(
            "tests/inputs/testVerticalMode.imcnp"
        )
        next(generator)
        next(generator)
        with self.assertRaises(mcnpy.errors.UnsupportedFeature):
            next(generator)

    def testCardStringRepr(self):
        in_str = "1 0 -1"
        card = mcnpy.input_parser.mcnp_input.Input(
            [in_str], mcnpy.input_parser.block_type.BlockType.CELL
        )
        self.assertEqual(str(card), "INPUT: BlockType.CELL")
        self.assertEqual(repr(card), "INPUT: BlockType.CELL: ['1 0 -1']")

    def testDataInputNameParsing(self):
        tests = {
            "kcOde": {"prefix": "kcode", "number": None, "classifier": None},
            "M300": {"prefix": "m", "number": 300, "classifier": None},
            "IMP:N,P,E": {
                "prefix": "imp",
                "number": None,
                "classifier": [Particle.NEUTRON, Particle.PHOTON, Particle.ELECTRON],
            },
            "F1004:n,P": {
                "prefix": "f",
                "number": 1004,
                "classifier": [Particle.NEUTRON, Particle.PHOTON],
            },
        }
        for in_str, answer in tests.items():
            # Testing parsing the names
            card = mcnpy.input_parser.mcnp_input.Input(
                [in_str], mcnpy.input_parser.block_type.BlockType.DATA
            )
            data_input = mcnpy.data_inputs.data_input.DataInput(card, fast_parse=True)
            self.assertEqual(data_input.prefix, answer["prefix"])
            if answer["number"]:
                self.assertEqual(data_input._input_number.value, answer["number"])
            if answer["classifier"]:
                self.assertEqual(
                    sorted(data_input.particle_classifiers),
                    sorted(answer["classifier"]),
                )

    def testDataInputNameEnforcement(self):
        tests = {
            "kcOde5": {"prefix": "kcode", "number": False, "classifier": 0},
            "M-300": {"prefix": "m", "number": True, "classifier": 0},
            "M": {"prefix": "m", "number": True, "classifier": 0},
            "f4m": {"prefix": "fm", "number": True, "classifier": 1},
            "IMP:N,P,E": {"prefix": "imp", "number": False, "classifier": 0},
            "IMP": {"prefix": "imp", "number": False, "classifier": 2},
        }
        valid = {
            "IMP:N,P,E": {"prefix": "imp", "number": False, "classifier": 2},
            "F1004:n,P": {"prefix": "f", "number": True, "classifier": 1},
        }
        # tests invalid names
        for in_str, answer in tests.items():
            with self.assertRaises(mcnpy.errors.MalformedInputError):
                card = mcnpy.input_parser.mcnp_input.Input(
                    [in_str], mcnpy.input_parser.block_type.BlockType.DATA
                )
                Fixture = DataInputTestFixture
                Fixture._class_prefix1 = answer["prefix"]
                Fixture._has_number1 = answer["number"]
                Fixture._has_classifier1 = answer["classifier"]
                card = Fixture(card)

        # tests valid names
        for in_str, answer in valid.items():
            card = mcnpy.input_parser.mcnp_input.Input(
                [in_str], mcnpy.input_parser.block_type.BlockType.DATA
            )
            print(card.input_lines)
            print(
                "Prefix",
                answer["prefix"],
                "number",
                answer["number"],
                "classifier",
                answer["classifier"],
            )
            Fixture = DataInputTestFixture
            Fixture._class_prefix1 = answer["prefix"]
            Fixture._has_number1 = answer["number"]
            Fixture._has_classifier1 = answer["classifier"]
            card = Fixture(card)

    def test_get_line_numbers(self):
        answers = {
            (5, 1, 60): 80,
            (6, 1, 0): 80,
            (6, 2, 0): 128,
            (6, 2, 3): 128,
            (6, 3, 0): 128,
            (7, 4, 0): 128,
        }
        for version, answer in answers.items():
            self.assertEqual(answer, mcnpy.constants.get_max_line_length(version))
        with self.assertRaises(mcnpy.errors.UnsupportedFeature):
            mcnpy.constants.get_max_line_length((5, 1, 38))

    def test_jump(self):
        jump = Jump()
        self.assertEqual("J", str(jump))
        jump2 = Jump()
        self.assertEqual(jump, jump2)
        with self.assertRaises(TypeError):
            bool(jump)

    def test_jump_and_a_hop(self):
        jump = Jump()
        # first you need to hop
        self.assertEqual("j", jump.lower())
        # then you need to skip
        self.assertEqual("Jump", jump.title())
        # before you can jump
        self.assertEqual("J", jump.upper())
        str(jump)
        repr(jump)


class TestClassifierNode(TestCase):
    def test_classifier_init(self):
        classifier = syntax_node.ClassifierNode()
        self.assertIsNone(classifier.prefix)
        self.assertIsNone(classifier.number)
        self.assertIsNone(classifier.particles)
        self.assertIsNone(classifier.modifier)
        self.assertIsNone(classifier.padding)

    def test_classifier_setter(self):
        classifier = syntax_node.ClassifierNode()
        classifier.prefix = syntax_node.ValueNode("M", str)
        self.assertEqual(classifier.prefix.value, "M")
        classifier.number = syntax_node.ValueNode("124", int)
        self.assertEqual(classifier.number.value, 124)
        classifier.modifier = syntax_node.ValueNode("*", str)
        self.assertEqual(classifier.modifier.value, "*")
        classifier.padding = syntax_node.PaddingNode(" ")
        self.assertEqual(len(classifier.padding.nodes), 1)

    def test_classifier_format(self):
        classifier = syntax_node.ClassifierNode()
        classifier.prefix = syntax_node.ValueNode("M", str)
        self.assertEqual(classifier.format(), "M")
        classifier.number = syntax_node.ValueNode("124", int)
        self.assertEqual(classifier.format(), "M124")
        classifier.modifier = syntax_node.ValueNode("*", str)
        self.assertEqual(classifier.format(), "*M124")
        classifier.padding = syntax_node.PaddingNode(" ")
        self.assertEqual(classifier.format(), "*M124 ")
        str(classifier)
        repr(classifier)

    def test_classifier_comments(self):
        classifier = syntax_node.ClassifierNode()
        classifier.prefix = syntax_node.ValueNode("M", str)
        self.assertEqual(len(list(classifier.comments)), 0)
        classifier.padding = syntax_node.PaddingNode(" ")
        classifier.padding.append("$ hi", True)
        self.assertEqual(len(list(classifier.comments)), 1)


class DataInputTestFixture(mcnpy.data_inputs.data_input.DataInputAbstract):
    _class_prefix1 = None
    _has_number1 = None
    _has_classifier1 = None

    def __init__(self, input_card=None):
        """
        :param input_card: the Card object representing this data input
        :type input_card: Input
        """
        super().__init__(input_card, fast_parse=True)

    def _class_prefix(self):
        return self._class_prefix1

    def _has_number(self):
        return self._has_number1

    def _has_classifier(self):
        return self._has_classifier1
