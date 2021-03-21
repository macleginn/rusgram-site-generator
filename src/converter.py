from typing import List
import TexSoup


IGNORED_NODES = {
    # Table components
    'toprule',
    'midrule',
    'bottomrule',
    'endhead'
}


class TOCNode:
    def __init__(self, title, label, number=None) -> None:
        self.title = title
        self.label = label
        self.number = number
        self.children = []


class TOC:
    '''A utility wrapper class for adding elements.'''

    def __init__(self) -> None:
        self.children = []

    def _add_to_level(self, level: int, node: TOCNode) -> None:
        '''
        Add a new section, subsection, etc. We do not want
        to manipulate the tree, so we always add to the last
        element on each level or fail if there is no suitable
        parent. This can be invoked directly, but convenience
        wrappers for predefined LaTeX hierarchy are also provided.
        '''
        if level < 1:
            raise ValueError(
                f'Incorrect level value: {level}; levels should be greater than or equal to 1.')
        current_root = self
        while level > 1:
            if not current_root.children:
                raise IndexError('No suitable parent found!')
            current_root = current_root.children[-1]
            level -= 1
        current_root.children.append(node)

    def add_section(self, node: TOCNode) -> None:
        self._add_to_level(1, node)

    def add_subsection(self, node: TOCNode) -> None:
        self._add_to_level(2, node)

    def add_subsubsection(self, node: TOCNode) -> None:
        self._add_to_level(3, node)

    def add_paragraph(self, node: TOCNode) -> None:
        self._add_to_level(4, node)


class Tex2HTMLConverter:
    '''
    A stateful tex2html converter. It is initialised with a tex-formatted
    string, which is passed to the TexSoup parser. A sequence of Tex
    elements is then converted to a sequence of malformed HTML-formatted nodes.
    Nodes are malformed because TexSoup does not handle paragraphs. Pieces of
    text including double newlines are returned as a single text element, and
    we have to add <p> and </p> tags based on internal state. HTML should become
    well-formed when all the elements are concatenated together.
    '''

    def __init__(self, tex_string: str) -> None:
        self.TOC = TOC()
        self.section_counter = 1
        self.subsection_counter = 1
        self.subsubsection_counter = 1
        self.paragraph_counter = 1
        self.example_counter = 1
        self.figure_counter = 1
        self.table_counter = 1

        # Cases of more complex context-dependent generation
        self.inside_paragraph = False
        self.tex_tree = TexSoup.TexSoup(tex_string)

        # End result
        self.HTML_arr = None

    # Helper methods for resetting counters

    def __start_new_section(self) -> None:
        self.subsection_counter = 1
        self.__start_new_subsection()

    def __start_new_subsection(self) -> None:
        self.subsubsection_counter = 1
        self.__start_new_subsubsection()

    def __start_new_subsubsection(self) -> None:
        self.paragraph_counter = 1

    def get_tree(self) -> TexSoup.data.TexNode:
        return self.tex_tree

    def __convert(self) -> None:
        '''Traverse the tree and emit HTML.'''
        if self.HTML_arr is not None:
            return
        result = []
        for node in self.tex_tree.contents:
            if type(node) == TexSoup.data.TexNode:
                if node.name in IGNORED_NODES:
                    continue
                elif node.name == 'tableofcontents':
                    # To be replaced with the actual TOC
                    # after parsing is done
                    result.append('>>> TOC <<<')
                else:
                    result.append(node.name)
            else:
                # The node is a string representing text.
                result.append('text')
        self.HTML_arr = result

    # Coverters for individual tags
    def section(self, contents, starred=False):
        result = '</p>' if self.inside_paragraph else ''
        self.inside_paragraph = False
        result += '\n'
        return f'\n<span class="small-caps">{contents}<span>'

    def subsection(self, contents, starred=False):
        pass

    def subsubsection(self, contents, starred=False):
        pass

    def paragraph(self, contents, starred=False):
        pass

    def textsc(self, contents):
        return f' <span class="small-caps">{contents}<span>'

    def textit(self, contents):
        return f' <span class="italics">{contents}<span>'

    def textbf(self, contents):
        return f' <span class="boldface">{contents}<span>'

    def longtable(self, node):
        # Parse node.args to get the number of columns.
        return ''

    def _get_HTML_arr(self) -> List[str]:
        if self.HTML_arr is None:
            self.__convert()
        return self.HTML_arr

    # The main API endpoint

    def get_HTML(self) -> str:
        if self.HTML_arr is None:
            self.__convert()
        return ''.join(self.HTML_arr)


if __name__ == '__main__':
    import os
    path = os.path.join(
        'content', 'coordination_pekelis_20130125_final_cleaned.tex')
    with open(path, 'r', encoding='utf-8') as inp:
        coverter_instance = Tex2HTMLConverter(inp.read().strip())
    print(sorted(set(coverter_instance._get_HTML_arr())))
