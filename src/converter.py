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
    'textsubscript',
    'textsuperscript',
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
            self.HTML_arr.append(postprocess(footnote))
        print(self.label_replacement_dict)

    def __convert_block(self, block, already_parsed=False) -> str:
        result = []
        # The block represents some LaTeX environment or a paragraph.
        if already_parsed:
            tree = block
        else:
            tree = TexSoup.TexSoup(block)
        # Is this a text node or one of special node types?
        first_node = tree.contents[0]
        if type(first_node) != TexSoup.data.TexNode or first_node.name in TEXT_NODES:
            # Do not add paragraph tags for pre-parsed elements.
            if not already_parsed:
                result.append('<p>')
            tmp = []
            self.__process_text_tree(tree, tmp)
            result.extend(tmp)
            if not already_parsed:
                result.append('</p>')
        elif first_node.name == 'BraceGroup':
            # An escape sequence
            result.append(first_node.contents[0])
        elif first_node.name in SECTION_NODES:
            tmp = []
            self.__process_text_tree(tree, tmp)
            result.extend(tmp)
        elif first_node.name == 'itemize':
            result.append(self.itemize(first_node))
        elif first_node.name == 'enumerate':
            result.append(self.enumerate(first_node))
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
                try:
                    result.append(node.text.strip())
                except AttributeError:
                    result.append(node.strip())
            else:
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
                elif node.name == 'textbackslash':
                    result.append('\\')
                elif node.name == 'section':
                    result.append(self.section(node))
                elif node.name == 'section*':
                    result.append(self.section(node, starred=True))
                elif node.name == 'subsection':
                    result.append(self.subsection(node))
                elif node.name == 'subsection*':
                    result.append(self.subsection(node, starred=True))
                elif node.name == 'subsubsection':
                    result.append(self.subsubsection(node))
                elif node.name == 'subsubsection*':
                    result.append(self.subsubsection(node, starred=True))
                # TODO: paragraph
                else:
                    result.append(
                        f'<span class="{node.name}">' + ' '.join(tmp) + '</span>')

    # Coverters for individual tags

    def section(self, node, starred=False):
        if not starred:
            section_no = self.section_counter
            section_id = f'section-{section_no}'
            self.last_generated_label = section_id
            self.section_counter += 1
            self.__start_new_section()
            section_id_attribute = f' id="{section_id}"'
            prefix = f'{section_no} '
        else:
            # Starred sections get no ids and cannot be referenced.
            section_id_attribute = ''
            prefix = ''
        tmp = []
        self.__process_text_tree(node, tmp)
        return f'<div class="section"{section_id_attribute}>{prefix}{" ".join(tmp)}</div>'

    def subsection(self, node, starred=False):
        if not starred:
            subsection_no = self.subsection_counter
            subsection_id = f'subsection-{self.section_counter-1}.{subsection_no}'
            self.last_generated_label = subsection_id
            self.subsection_counter += 1
            self.__start_new_subsection()
            subsection_id_attribute = f' id="{subsection_id}"'
            prefix = f'{self.section_counter-1}.{subsection_no} '
        else:
            # Starred sections get no ids and cannot be referenced.
            subsection_id_attribute = ''
            prefix = ''
        tmp = []
        self.__process_text_tree(node, tmp)
        return f'<div class="subsection"{subsection_id_attribute}>{prefix}{" ".join(tmp)}</div>'

    def subsubsection(self, node, starred=False):
        if not starred:
            subsubsection_no = self.subsubsection_counter
            subsubsection_id = f'subsubsection-{self.section_counter-1}.{self.subsection_counter-1}.{subsubsection_no}'
            self.last_generated_label = subsubsection_no
            self.subsubsection_counter += 1
            self.__start_new_subsubsection()
            subsubsection_id_attribute = f' id="{subsubsection_id}"'
            prefix = f'{self.section_counter-1}.{self.subsection_counter-1}.{subsubsection_no} '
        else:
            # Starred sections get no ids and cannot be referenced.
            subsubsection_id_attribute = ''
            prefix = ''
        tmp = []
        self.__process_text_tree(node, tmp)
        return f'<div class="subsubsection"{subsubsection_id_attribute}>{prefix}{" ".join(tmp)}</div>'

    def paragraph(self, contents, starred=False):
        pass

    def itemize(self, node):
        result = []
        for child in node.children:
            # Each child is an item
            tmp = []
            for item_element in child.contents:
                # This can be either a text node or an embedded environment.
                # self.__convert_block can take care of either.
                item_tree = empty_tree()
                item_tree.append(item_element)
                tmp.append(self.__convert_block(item_tree, True))
            result.append(f'<li>{" ".join(tmp)}</li>')
        return f'<ul>{" ".join(result)}</ul>'

    def enumerate(self, node):
        result = []
        # Check if the node is an example group and set the counter.
        # For an example group the following code is produced by pandoc:
        # ```latex
        # \begin{enumerate}
        # \def\labelenumi{(\arabic{enumi})}
        # \setcounter{enumi}{1}                   % Here's where the counter is set.
        # \item
        #         Мой друг ― доктор из Италии по Интернету посоветовал \textit{мазь} и
        #         \textit{попить антибиотик}. {[}коллективный. Хватит губить детей!
        #         (2011){]}
        # \item
        #         Хочется, потому что туда обещали \textit{дрова} \textit{и табаку}.
        #         {[}Д.~Быков. Орфография (2002){]}
        # \end{enumerate}
        # ```
        first_example_no = None
        class_attribute = ''
        if node.children[0].name == 'def':
            class_attribute = f' class="example"'
            first_example_no = 1
        if len(node.children) >= 3 and node.children[2].name == 'setcounter':
            first_example_no = int(node.children[2].args[1].contents[0]) + 1
        for child in node.children:
            if child.name != 'item':
                continue
            tmp = []
            for item_element in child.contents:
                # This can be either a text node or an embedded environment.
                # self.__convert_block can take care of either.
                item_tree = empty_tree()
                item_tree.append(item_element)
                tmp.append(self.__convert_block(item_tree, True))
            if first_example_no is None:
                # This is a regular list
                result.append(f'<li>{" ".join(tmp)}</li>')
            else:
                # This is an example list; we need to supply numbers ourselves
                result.append(f'<li>({first_example_no}) {" ".join(tmp)}</li>')
                first_example_no += 1
        return f'<ol{class_attribute}>{" ".join(result)}</ol>'

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


def empty_tree():
    return TexSoup.TexSoup('')


def preprocess(txt):
    preprocessing_dict = {
        # Preserve intentional spaces
        '\\textless{} ': '&lt;_',
        '\\textless{}': '&lt;',
        '\\textless ': '&lt;_',
        '\\textless': '&lt;',
        ' \\textgreater{}': '_&gt;',
        '\\textgreater{}': '&gt;',
        ' \\textgreater': '_&gt;',
        '\\textgreater': '&gt;',
        '\\ldots{}': '…',
        '\\ldots': '…',
        '\\_': '_',
        '\\#': '#',
        '---': '—',
        ' -- ': ' — ',
        '--': '–',
        '~': '&nbsp;',
        ' —': '&nbsp;—'
    }
    for k, v in preprocessing_dict.items():
        txt = txt.replace(k, v)
    return txt


def postprocess(txt):
    postprocessing_dict = {
        '> .': '>.',
        '&gt; .': '&gt;.',
        '> »': '>»',
        '&gt; »': '&gt;»',
        '> ,': '>,',
        '&gt; ,': '&gt;,',
        '> ;': '>;',
        '&gt; ;': '&gt;;',
        '> ?': '>?',
        '&gt; ?': '&gt;?',
        '> !': '>!',
        '&gt; !': '&gt;!',
        '> )': '>)',
        '&gt; )': '&gt;)',
        '( <': '(<',
        '( &lt;': '(&lt;',
        '* <': '*<',
        '* &lt;': '*&lt;',
        '`': '‘',
        "'": '’',
        "&nbsp; ": '&nbsp;',
        '[</span> ': '[</span>',
        ' <span class="BraceGroup">]': '<span class="BraceGroup">]',
        ' <span id="foot': '<span id="foot',
        '[ ': '[',
        ' ]': ']',
        '( ': '(',
        ' )': ')',
        '&lt; ': '&lt;',
        ' &gt;': '&gt;',
        '<sup>?</sup> ': '<sup>?</sup>',
        # Restore intentional spaces
        '&lt;_': '&lt; ',
        '_&gt;': ' &gt;'
    }
    for k, v in postprocessing_dict.items():
        txt = txt.replace(k, v)
    return txt


def convert_example(txt, example_number):
    return f'({example_number}): {txt}'


if __name__ == '__main__':
    import os
    opj = os.path.join
    path = opj('content', 'coordination_pekelis_20130125_final_cleaned.tex')
    with open(path, 'r', encoding='utf-8') as inp:
        coverter_instance = Tex2HTMLConverter(inp.read().strip())
    with open(opj('public', 'out.html'), 'w', encoding='utf-8') as out:
        with open(opj('templates', 'header.html'), 'r', encoding='utf-8') as inp:
            header = inp.read()
        with open(opj('templates', 'base.html'), 'r', encoding='utf-8') as inp:
            template = inp.read()
            out.write(
                template.replace(
                    '{{main}}',
                    '\n'.join(coverter_instance._get_HTML_arr())
                ).replace('{{header}}', header)
            )
