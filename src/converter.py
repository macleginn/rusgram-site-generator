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
SECTION_NODES = {
    'section',
    'section*',
    'subsection',
    'subsection*',
    'subsubsection',
    'subsubsection*',
    'paragraph',
    'paragraph*'
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
        self.footnotes = []
        self.label_replacement_dict = {}
        self.last_generated_label = None

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
        for footnote in self.footnotes:
            self.HTML_arr.append(footnote)
        print(self.label_replacement_dict)

    def __convert_block(self, block):
        result = []
        # The block represents some LaTeX environment or a paragraph.
        tree = TexSoup.TexSoup(block)
        # Is this a text node or one of special node types?
        first_node = tree.contents[0]
        if type(first_node) != TexSoup.data.TexNode or first_node.name in TEXT_NODES:
            result.append('<p>')
            tmp = []
            self.__process_text_tree(tree, tmp)
            result.extend(tmp)
            result.append('</p>')
        elif first_node.name in SECTION_NODES:
            tmp = []
            self.__process_text_tree(tree, tmp)
            result.extend(tmp)
        else:
            result.append(first_node.name)
        return ' '.join(result)

    def __process_text_tree(self, tree, result):
        """
        process_text_tree iterates over the tree's contents, adds text nodes, and
        recursively expands and adds contents of simple markup nodes. It does not
        expect to see nodes that cannot be dealt with by specifying a pair of opening
        and closing tags, except for footnotes, which are replaced with a footnote anchor.
        The text of the footnote itself is stored for later.
        """
        for node in tree.contents:
            if type(node) != TexSoup.data.TexNode:
                result.append(node.text.strip())
            else:
                print(node.name)
                tmp = []
                self.__process_text_tree(node, tmp)
                if node.name == 'label':
                    self.label_replacement_dict[node.text[0]
                                                ] = self.last_generated_label
                elif node.name == 'footnote':
                    footnote_no = len(self.footnotes) + 1
                    result.append(
                        f'<span id="footnoteanchor{footnote_no}"><sup><a href="#footnote{footnote_no}">{footnote_no}</a></sup></span>')
                    self.footnotes.append(
                        f'<div id="footnote{footnote_no}" class="footnote"><sup><a href="#footnoteanchor{footnote_no}">{footnote_no}</a></sup> ' + ' '.join(tmp) + '</div>')
                elif node.name == 'textsuperscript':
                    result.append(
                        f'<sup>' + ' '.join(tmp) + '</sup>')
                elif node.name == 'textsubscript':
                    result.append(
                        f'<sub>' + ' '.join(tmp) + '</sub>')
                elif node.name == 'section':
                    result.append(self.section(node))
                elif node.name == 'section*':
                    result.append(self.section(node, starred=True))
                else:
                    result.append(
                        f'<span class="{node.name}">' + ' '.join(tmp) + '</span>')

    # Coverters for individual tags

    def section(self, node, starred=False):
        section_no = self.section_counter
        section_id = f'section-{section_no}'
        self.last_generated_label = section_id
        self.section_counter += 1
        self.__start_new_section()
        if starred:
            prefix = ''
        else:
            prefix = f'{section_no} '
        tmp = []
        self.__process_text_tree(node, tmp)
        return f'<div class="section" id="{section_id}">{prefix}{" ".join(tmp)}</div>'

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
        "&nbsp; ": '&nbsp;',
        '[</span> ': '[</span>',
        ' <span class="BraceGroup">]': '<span class="BraceGroup">]',
        ' <span id="foot': '<span id="foot'
    }
    for k, v in postprocessing_dict.items():
        txt = txt.replace(k, v)
    return txt


def convert_example(txt, example_number):
    return f'({example_number}): {txt}'


if __name__ == '__main__':
    import os
    path = os.path.join(
        'content', 'coordination_pekelis_20130125_final_cleaned.tex')
    with open(path, 'r', encoding='utf-8') as inp:
        coverter_instance = Tex2HTMLConverter(inp.read().strip())
    with open('out.html', 'w', encoding='utf-8') as out:
        with open('template.html', 'r', encoding='utf-8') as inp:
            template = inp.read()
            out.write(template.replace('{{main}}', '\n'.join(
                coverter_instance._get_HTML_arr())))
