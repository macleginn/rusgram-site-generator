import re
from typing import List
import TexSoup


IGNORED_NODES = {
    # Table components
    'toprule',
    'midrule',
    'bottomrule',
    'endhead'
}
TEXT_NODES = {
    'underline',
    'textit',
    'textbf',
    'textsc',
    'texttt',
    'it',
    'bf',
    'sc',
    'tt'
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
    string. The string is split into blocks separated by 2+ whitespaces,
    and the blocks are then processed one by one. Blocks not starting with
    Tex commands are treated as paragraphs of text.
    '''

    def __init__(self, tex_string: str) -> None:
        # Bookkeeping
        self.TOC = TOC()
        self.section_counter = 1
        self.subsection_counter = 1
        self.subsubsection_counter = 1
        self.paragraph_counter = 1
        self.example_counter = 1
        self.figure_counter = 1
        self.table_counter = 1

        # We need this step to cleanly take care of paragraphs
        # and other elements, such as \ex. blocks, that TexSoup
        # does not handle correctly.
        self.blocks = re.split(r'[\n\r]{2,}', preprocess(tex_string))

        # End result
        self.HTML_arr = None
        self.__convert()

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
        if self.HTML_arr is not None:
            return
        result = []
        for block in self.blocks:
            if block.startswith('\\ex'):
                # A glossed example; we use a custom parser for this
                result.append(convert_example(block, self.example_counter))
                self.example_counter += 1
            elif block.startswith('\\tableofcontents'):
                # To be replaced with the actual TOC
                # after parsing is done
                result.append('<p>TOC</p>')
            # More special cases will certainly turn up
            else:
                result.append(postprocess(self.__convert_block(block)))
        self.HTML_arr = result

    def __convert_block(self, block):
        result = []
        # The block represents some LaTeX environment or a paragraph.
        tree = TexSoup.TexSoup(block)
        # Is this a text paragraph or one of special node types?
        first_node = tree.contents[0]
        if type(first_node) != TexSoup.data.TexNode or first_node.name in TEXT_NODES:
            result.append('<p>')
            tmp = []
            process_text_tree(tree, tmp)
            result.extend(tmp)
            result.append('</p>')
        else:
            result.append(first_node.name)
        return ' '.join(result)

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


def preprocess(txt):
    preprocessing_dict = {
        '\\textless{}': '&lt;',
        '\\textless': '&lt;',
        '\\textgreater{}': '&gt;',
        '\\textgreater': '&gt;',
        '\\ldots{}': '…',
        '\\_': '_',
        '\\#': '#',
        '---': '—',
        ' -- ': ' — ',
        '--': '–',
        '~': '&nbsp;'
    }
    for k, v in preprocessing_dict.items():
        txt = txt.replace(k, v)
    return txt


def postprocess(txt):
    postprocessing_dict = {
        '> .': '>.',
        '> »': '>»',
        '> ,': '>,',
        '> ;': '>;',
        '> ?': '>?',
        '> !': '>!',
        '> )': '>)',
        '( <': '(<',
        '* <': '*<',
        '`': '‘',
        "'": '’',
        '[</span> ': '[</span>',
        ' <span class="BraceGroup">]': '<span class="BraceGroup">]'
    }
    for k, v in postprocessing_dict.items():
        txt = txt.replace(k, v)
    return txt


def process_text_tree(tree, result):
    """
    process_text_tree iterates over the tree's contents, adds text nodes, and
    recursively expands and adds contents of simple markup nodes. It does not
    expect to see nodes that cannot be dealt with by specifying some CSS on 
    a span and will raise en error if it sees them.
    """
    for node in tree.contents:
        if type(node) != TexSoup.data.TexNode:
            result.append(node.text.strip())
        else:
            tmp = []
            process_text_tree(node, tmp)
            if node.name == 'footnote':
                result.append(
                    f'<div class="{node.name}">' + ' '.join(tmp) + '</div>')
            elif node.name == 'textsuperscript':
                result.append(
                    f'<sup>' + ' '.join(tmp) + '</sup>')
            elif node.name == 'textsubscript':
                result.append(
                    f'<sub>' + ' '.join(tmp) + '</sub>')
            else:
                result.append(
                    f'<span class="{node.name}">' + ' '.join(tmp) + '</span>')


def convert_example(txt, example_number):
    return f'({example_number}): {txt}'


if __name__ == '__main__':
    import os
    path = os.path.join(
        'content', 'coordination_pekelis_20130125_final_cleaned.tex')
    with open(path, 'r', encoding='utf-8') as inp:
        coverter_instance = Tex2HTMLConverter(inp.read().strip())
    for el in coverter_instance._get_HTML_arr():
        print(el)
        print()
