# Copyright 2024, Battelle Energy Alliance, LLC All Rights Reserved.
from montepy.constants import MAX_ATOMIC_SYMBOL_LENGTH
from montepy.data_inputs.element import Element
from montepy.errors import *
from montepy.input_parser.syntax_node import ValueNode

import re


class Isotope:
    """
    A class to represent an MCNP isotope

    :param ZAID: the MCNP isotope identifier
    :type ZAID: str
    """

    #                   Cl-52      Br-101     Xe-150      Os-203    Cm-251     Og-296
    _BOUNDING_CURVE = [(17, 52), (35, 101), (54, 150), (76, 203), (96, 251), (118, 296)]
    """
    Points on bounding curve for determining if "valid" isotope
    """

    _NAME_PARSER = re.compile(
        r"""(
                (?P<ZAID>\d{4,6})|
                ((?P<element>[a-z]+)-?(?P<A>\d*))
            )
            (m(?P<meta>\d+))?
            (\.(?P<library>\d{2,}[a-z]+))?""",
        re.I | re.VERBOSE,
    )
    """"""

    def __init__(
        self,
        ZAID="",
        element=None,
        Z=None,
        A=None,
        meta_state=None,
        library="",
        node=None,
    ):
        if node is not None and isinstance(node, ValueNode):
            if node.type == float:
                node = ValueNode(node.token, str, node.padding)
            self._tree = node
            ZAID = node.value
        if ZAID:
            parts = ZAID.split(".")
            try:
                assert len(parts) <= 2
                int(parts[0])
            except (AssertionError, ValueError) as e:
                raise ValueError(f"ZAID: {ZAID} could not be parsed as a valid isotope")
            self._ZAID = parts[0]
            new_vals = self._parse_zaid(int(self._ZAID))
            for key, value in new_vals.items():
                setattr(self, key, value)
            if len(parts) == 2:
                self._library = parts[1]
            else:
                self._library = ""
            return
        elif element is not None:
            if not isinstance(element, Element):
                raise TypeError(
                    f"Only type Element is allowed for element argument. {element} given."
                )
            self._element = element
            self._Z = self._element.Z
        elif Z is not None:
            if not isinstance(Z, int):
                raise TypeError(f"Z number must be an int. {Z} given.")
            self._Z = Z
            self._element = Element(Z)
        if A is not None:
            if not isinstance(A, int):
                raise TypeError(f"A number must be an int. {A} given.")
            self._A = A
        else:
            self._A = 0
        if not isinstance(meta_state, (int, type(None))):
            raise TypeError(f"Meta state must be an int. {meta_state} given.")
        if meta_state:
            self._is_metastable = True
            self._meta_state = meta_state
        else:
            self._is_metastable = False
            self._meta_state = None
        if not isinstance(library, str):
            raise TypeError(f"Library can only be str. {library} given.")
        self._library = library
        self._ZAID = str(self.get_full_zaid())

    @classmethod
    def _parse_zaid(cls, ZAID):
        """
        Parses the ZAID fully including metastable isomers.

        See Table 3-32 of LA-UR-17-29881

        """

        def is_probably_an_isotope(Z, A):
            for lim_Z, lim_A in cls._BOUNDING_CURVE:
                if Z <= lim_Z:
                    if A <= lim_A:
                        return True
                    else:
                        return False
                else:
                    continue
            # if you are above Lv it's probably legit.
            return True

        ret = {}
        ret["_Z"] = int(ZAID / 1000)
        ret["_element"] = Element(ret["_Z"])
        A = int(ZAID % 1000)
        if not is_probably_an_isotope(ret["_Z"], A):
            ret["_is_metastable"] = True
            true_A = A - 300
            # only m1,2,3,4 allowed
            found = False
            for i in range(1, 5):
                true_A -= 100
                # assumes that can only vary 40% from A = 2Z
                if is_probably_an_isotope(ret["_Z"], true_A):
                    found = True
                    break
            if found:
                ret["_meta_state"] = i
                ret["_A"] = true_A
            else:
                raise ValueError(
                    f"ZAID: {ZAID} cannot be parsed as a valid metastable isomer. "
                    "Only isomeric state 1 - 4 are allowed"
                )

        else:
            ret["_is_metastable"] = False
            ret["_meta_state"] = None
            ret["_A"] = A
        return ret

    @property
    def ZAID(self):
        """
        The ZZZAAA identifier following MCNP convention

        :rtype: int
        """
        # if this is made mutable this cannot be user provided, but must be calculated.
        return self._ZAID

    @property
    def Z(self):
        """
        The Z number for this isotope.

        :returns: the atomic number.
        :rtype: int
        """
        return self._Z

    @property
    def A(self):
        """
        The A number for this isotope.

        :returns: the isotope's mass.
        :rtype: int
        """
        return self._A

    @property
    def element(self):
        """
        The base element for this isotope.

        :returns: The element for this isotope.
        :rtype: Element
        """
        return self._element

    @property
    def is_metastable(self):
        """
        Whether or not this is a metastable isomer.

        :returns: boolean of if this is metastable.
        :rtype: bool
        """
        return self._is_metastable

    @property
    def meta_state(self):
        """
        If this is a metastable isomer, which state is it?

        Can return values in the range [1,4] (or None). The exact state
        number is decided by who made the ACE file for this, and not quantum mechanics.
        Convention states that the isomers should be numbered from lowest to highest energy.

        :returns: the metastable isomeric state of this "isotope" in the range [1,4], or None
                if this is a ground state isomer.
        :rtype: int
        """
        return self._meta_state

    @property
    def library(self):
        """
         The MCNP library identifier e.g. 80c

        :rtype: str
        """
        return self._library

    @library.setter
    def library(self, library):
        if not isinstance(library, str):
            raise TypeError("library must be a string")
        self._library = library

    def __str__(self):
        return f"{self.element.symbol:>2}-{self.A:<3} ({self._library})"

    def mcnp_str(self):
        """
        Returns an MCNP formatted representation.

        E.g., 1001.80c

        :returns: a string that can be used in MCNP
        :rtype: str
        """
        return f"{self.ZAID}.{self.library}"

    def get_base_zaid(self):
        """
        Get the ZAID identifier of the base isotope this is an isomer of.

        This is mostly helpful for working with metastable isomers.

        :returns: the mcnp ZAID of the ground state of this isotope.
        :rtype: int
        """
        return self.Z * 1000 + self.A

    def get_full_zaid(self):
        """
        Get the ZAID identifier of this isomer.

        :returns: the mcnp ZAID of this isotope.
        :rtype: int
        """
        meta_adder = 300 + 100 * self.meta_state if self.is_metastable else 0
        return self.Z * 1000 + self.A + meta_adder

    @classmethod
    def get_from_fancy_name(cls, identifier):
        """
        :param identifier:
        :type idenitifer: str | int
        """
        A = 0
        isomer = None
        base_meta = 0
        library = ""
        if isinstance(identifier, (int, float)):
            parts = cls._parse_zaid(int(identifier))
            element, A, isomer = (
                parts["_element"],
                parts["_A"],
                parts["_meta_state"],
            )
        elif isinstance(identifier, str):
            if match := cls._NAME_PARSER.match(identifier):
                match = match.groupdict()
                if match["ZAID"]:
                    parts = cls._parse_zaid(int(match["ZAID"]))
                    element, A, base_meta = (
                        parts["_element"],
                        parts["_A"],
                        parts["_meta_state"],
                    )

                else:
                    element_name = match["element"]
                    if len(element_name) <= MAX_ATOMIC_SYMBOL_LENGTH:
                        element = Element.get_by_symbol(element_name.capitalize())
                    else:
                        element = Element.get_by_name(element_name.lower())
                    if match["A"]:
                        A = int(match["A"])
                if match["meta"]:
                    isomer = int(match["meta"])
                    if base_meta:
                        isomer += base_meta
                if match["library"]:
                    library = match["library"]
        # handle the tuple case
        elif isinstance(identifier, (tuple, list)):
            if len(identifier) == 0:
                raise ValueError(f"0-length identifiers not allowed.")
            # handle element
            element = identifier[0]
            if isinstance(element, int):
                element = Element(element)
            elif isinstance(element, str):
                if len(element) <= MAX_ATOMIC_SYMBOL_LENGTH:
                    element = Element.get_by_symbol(element.capitalize())
                else:
                    element = Element.get_by_name(element.lower())
            elif not isinstance(element, Element):
                raise TypeError(
                    f"Element identifier must be int, str, or Element. {identifier[0]} given."
                )
            # handle A
            if len(identifier) >= 2:
                if not isinstance(identifier[1], int):
                    raise TypeError(f"A number must be an int. {identifier[1]} given.")
                A = identifier[1]
            # handle isomer
            if len(identifier) >= 3:
                if not isinstance(identifier[1], int):
                    raise TypeError(
                        f"Isomeric state number must be an int. {identifier[1]} given."
                    )
                isomer = identifier[2]
            # handle library
            if len(identifier) == 4:
                if not isinstance(identifier[3], str):
                    raise TypeError(f"Library must be a str. {identifier[3]} given.")
                library = identifier[3]
        else:
            raise TypeError(
                f"Isotope fancy names only supports str, ints, and iterables. {identifier} given."
            )

        return cls(element=element, A=A, meta_state=isomer, library=library)

    def __repr__(self):
        return f"ZAID={self.ZAID}, Z={self.Z}, A={self.A}, element={self.element}, library={self.library}"

    def __hash__(self):
        return hash(self._ZAID)

    def __lt__(self, other):
        return int(self.ZAID) < int(other.ZAID)

    def __format__(self, format_str):
        return str(self).__format__(format_str)
