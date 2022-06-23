from abc import ABC, abstractmethod
from mcnpy.input_parser.constants import BLANK_SPACE_CONTINUE, get_max_line_length
from mcnpy.input_parser.mcnp_input import Comment
import mcnpy
import textwrap


class MCNP_Card(ABC):
    """
    Abstract class for semantic representations of MCNP input cards.
    """

    def __init__(self, input_card, comments=None):
        """
        :param input_card: The Card syntax object this will wrap and parse.
        :type input_card: Card
        :param comment: The Comments that proceeded this card or were inside of this if any
        :type Comment: list
        """
        self._problem = None
        if input_card:
            assert isinstance(input_card, mcnpy.input_parser.mcnp_input.Card)
            assert isinstance(comments, (list, Comment, type(None)))
            if isinstance(comments, list):
                for comment in comments:
                    assert isinstance(comment, Comment)
            elif isinstance(comments, Comment):
                comments = [comments]
            self._input_lines = input_card.input_lines
            self._mutated = False
        else:
            self._input_lines = []
            self._mutated = True
        if comments:
            self._comments = comments
        else:
            self._comments = []

    @abstractmethod
    def format_for_mcnp_input(self, mcnp_version):
        """
        Creates a string representation of this card that can be
        written to file.

        :param mcnp_version: The tuple for the MCNP version that must be exported to.
        :type mcnp_version: tuple
        :return: a list of strings for the lines that this card will occupy.
        :rtype: list
        """
        ret = []
        if self.comments:
            if not self.mutated:
                ret += self.comments[0].format_for_mcnp_input(mcnp_version)
            else:
                for comment in self.comments:
                    ret += comment.format_for_mcnp_input(mcnp_version)
        return ret

    def _format_for_mcnp_unmutated(self, mcnp_version):
        """
        Creates a string representation of this card that can be
        written to file when the card did not mutate.

        TODO add to developer's guide.

        :param mcnp_version: The tuple for the MCNP version that must be exported to.
        :type mcnp_version: tuple
        :return: a list of strings for the lines that this card will occupy.
        :rtype: list
        """
        ret = []
        comments_dict = {}
        if self.comments:
            for comment in self.comments:
                if comment.is_cutting_comment:
                    comments_dict[comment.card_line] = comment
            ret += self.comments[0].format_for_mcnp_input(mcnp_version)
        for i, line in enumerate(self.input_lines):
            if i in comments_dict:
                ret += comments_dict[i].format_for_mcnp_input(mcnp_version)
            ret.append(line)
        return ret

    @property
    def comments(self):
        """
        The preceding comment block to this card if any.

        :rtype: Comment
        """
        return self._comments

    @comments.setter
    def comments(self, comments):
        assert isinstance(comments, list)
        for comment in comments:
            assert isinstance(comment, Comment)
        self._mutated = True
        self._comments = comments

    @comments.deleter
    def comments(self):
        self._comment = []

    @property
    def input_lines(self):
        """The raw input lines read from the input file

        :rtype: list
        """
        return self._input_lines

    @property
    def mutated(self):
        """True if the user has changed a property of this card

        :rtype: bool
        """
        return self._mutated

    @staticmethod
    def wrap_words_for_mcnp(words, mcnp_version, is_first_line):
        """
        Wraps the list of the words to be a well formed MCNP input.

        multi-line cards will be handled by using the indentation format,
        and not the "&" method.

        :param words: A list of the "words" or data-grams that needed to added to this card.
                      Each word will be separated by at least one space.
        :type words: list
        :param mcnp_version: the tuple for the MCNP that must be formatted for.
        :type mcnp_version: tuple
        :param is_first_line: If true this will be the beginning of an MCNP card.
                             The first line will not be indented.
        :type is_first_line: bool
        :returns: A list of strings that can be written to an input file, one item to a line.
        :rtype: list
        """
        string = " ".join(words)
        return MCNP_Card.wrap_string_for_mcnp(string, mcnp_version, is_first_line)

    @staticmethod
    def wrap_string_for_mcnp(string, mcnp_version, is_first_line):
        """
        Wraps the list of the words to be a well formed MCNP input.

        multi-line cards will be handled by using the indentation format,
        and not the "&" method.

        :param string: A long string that needs to be chunked appropriately for MCNP inputs
        :type string: str
        :param mcnp_version: the tuple for the MCNP that must be formatted for.
        :type mcnp_version: tuple
        :param is_first_line: If true this will be the beginning of an MCNP card.
                             The first line will not be indented.
        :type is_first_line: bool
        :returns: A list of strings that can be written to an input file, one item to a line.
        :rtype: list
        """
        line_length = get_max_line_length(mcnp_version)
        indent_length = BLANK_SPACE_CONTINUE
        if is_first_line:
            initial_indent = 0
        else:
            initial_indent = indent_length
        wrapper = textwrap.TextWrapper(
            width=line_length,
            initial_indent=" " * initial_indent,
            subsequent_indent=" " * indent_length,
        )
        return wrapper.wrap(string)

    def link_to_problem(self, problem):
        """Links the card to the parent problem for this card.

        This is done so that cards can find links to other objects.

        :param problem: The problem to link this card to.
        :type type: MCNP_Problem
        """
        assert isinstance(problem, mcnpy.mcnp_problem.MCNP_Problem)
        self._problem = problem
