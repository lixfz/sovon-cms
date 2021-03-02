import argparse
import logging
import os
import os.path as path
import re
import shutil

import markdown as md
from jinja2 import Environment as JinjaEnv, FileSystemLoader as JinjaFSLoader

from sovon_cms.version import __version__

module_name = str(path.basename(__file__)).split('.')[0]
logger = logging.getLogger(module_name)

MAX_INDEX = int(1e10)

REVERSE_SORT_INDEX = int(1e4)

MARKDOWN_EXTENSIONS = ['markdown.extensions.extra',
                       # 'markdown.extensions.codehilite',
                       'markdown.extensions.tables',
                       'markdown.extensions.toc',
                       'markdown_katex',
                       ]
MARKDOWN_EXTENSION_CONFIGS = {'markdown_katex': {'no_inline_svg': True,  # fix for WeasyPrint
                                                 'insert_fonts_css': True,
                                                 },
                              }
MARKDOWN_TEMPLATE = '_markdown.html'
INDEX_TEMPLATE = '_index.html'


def parse_file_name(file_name):
    p = re.match(r'(\d+)[\-\._](.+)', file_name)
    if p:
        index, title = int(p.groups()[0]), p.groups()[1]
    else:
        index, title = MAX_INDEX, file_name

    title, _ = path.splitext(title)
    return index, title


def read_file(file_path) -> str:
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def write_file(file_path, content):
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)


def parse_markdown(file_path) -> str:
    s = read_file(file_path)
    r = md.markdown(s, extensions=MARKDOWN_EXTENSIONS, extension_configs=MARKDOWN_EXTENSION_CONFIGS)
    return r


def parse_jinja(file_path, **kwargs):
    root_path, template = path.split(file_path)
    env = JinjaEnv(loader=JinjaFSLoader(root_path))
    r = env.get_template(template).render(**kwargs)
    return r


class Document(object):
    def __init__(self, file_path):
        assert path.exists(file_path)

        self.file_path = file_path
        self.modified_time = os.stat(file_path).st_mtime
        self.is_markdown = file_path.endswith('.md')
        self.is_html = file_path.endswith('.html') or file_path.endswith('.htm')

        dir_path, file_name = path.split(file_path)
        if self.is_markdown:
            self.index, self.title = parse_file_name(file_name)
        else:
            self.index, self.title = None, file_name

    @property
    def summary(self) -> str:
        raise NotImplementedError()

    @property
    def content(self) -> str:
        return read_file(self.file_path)

    @property
    def html(self) -> str:
        if self.is_markdown:
            return md.markdown(self.content, extensions=MARKDOWN_EXTENSIONS)
        else:
            raise ValueError(f'"html" is not supported for file {self.title}')

    @property
    def href(self):
        _, file_name = path.split(self.file_path)
        if self.is_markdown:
            file_name = re.sub(r'\.md$', '.html', file_name)
        return file_name

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(index={self.index}, title="{self.title}")'


class Category(object):
    def __init__(self, dir_path, index=None, title=None, parent=None):
        self.dir_path = dir_path

        if index is None and title is None:
            _, category_dir = path.split(dir_path)
            self.index, self.title = parse_file_name(category_dir)
        else:
            self.index = index
            self.title = title

        document_template = path.join(dir_path, MARKDOWN_TEMPLATE)
        index_template = path.join(dir_path, INDEX_TEMPLATE)

        if parent is not None:
            self.document_template = document_template if path.exists(document_template) \
                else parent.document_template
            self.index_template = index_template if path.exists(index_template) \
                else parent.index_template
        else:
            self.document_template = document_template if path.exists(document_template) else None
            self.index_template = index_template if path.exists(index_template) else None

        self.parent = parent

        # cached items
        self.documents_ = None
        self.children_ = None
        self.modified_time_ = None

    @property
    def uri(self):
        _, category_dir = path.split(self.dir_path)
        if self.parent is not None:
            return f'{self.parent.uri}/{category_dir}'
        else:
            return ''

    @property
    def modified_time(self):
        if self.modified_time_ is None:
            document_times = [doc.modified_time for doc in self.documents]
            # children_times = [child.modified_time for child in self.children]
            # all_times = document_times + children_times
            all_times = document_times
            self.modified_time_ = max(all_times) if all_times else os.stat(self.dir_path).st_mtime

        return self.modified_time_

    @property
    def documents(self) -> list:
        if self.documents_ is None:
            sub_dirs = [path.join(self.dir_path, p) for p in os.listdir(self.dir_path)
                        if p not in {INDEX_TEMPLATE, MARKDOWN_TEMPLATE}]
            sub_dirs = filter(path.isfile, sub_dirs)
            self.documents_ = list(map(Document, sub_dirs))

        return self.documents_

    @property
    def children(self) -> list:
        if self.children_ is None:
            sub_dirs = [path.join(self.dir_path, p) for p in os.listdir(self.dir_path)]
            sub_dirs = filter(path.isdir, sub_dirs)
            self.children_ = [Category(sub, parent=self) for sub in sub_dirs]

        return self.children_

    @property
    def has_html(self):
        return any(doc.is_markdown or doc.is_html for doc in self.documents)

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(index={self.index}, title="{self.title}")'


def is_ready(output_path, time_stamp):
    return os.path.exists(output_path) and os.stat(output_path).st_mtime > time_stamp


def render_site(root_dir, output_dir):
    root_dir = path.abspath(path.expanduser(root_dir))
    output_dir = path.abspath(path.expanduser(output_dir))
    assert path.exists(root_dir), f'Not found path {root_dir}'
    assert path.isdir(root_dir), f'Root path should be a directory'
    if not path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    else:
        assert path.isdir(output_dir), f'Output path should be a directory'

    logger.info(f'render site from "{root_dir}" to "{output_dir}"')
    root = Category(root_dir, 0, 'ROOT')
    render_category(root, root, output_dir)
    logger.info('done')


def render_category(root: Category, category: Category, output_dir: str):
    # logger.info(f'[{category.title}] rendering ...')

    if not path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    children = category.children
    documents = category.documents
    index_template = category.index_template
    markdown_template = category.document_template

    children_with_html = [cat for cat in children if cat.has_html]
    markdown_documents = [doc for doc in documents if doc.is_markdown]
    markdown_documents.sort(key=lambda doc: doc.index if doc.index is not None else MAX_INDEX,
                            reverse=all([doc.index is not None and doc.index > REVERSE_SORT_INDEX
                                         for doc in markdown_documents]))

    counter = 0
    if index_template is not None and len(markdown_documents) > 0:
        output_path = path.join(output_dir, 'index.html')
        if not is_ready(output_path, category.modified_time):
            logger.info(f'updating {output_path}')
            content = parse_jinja(index_template, documents=markdown_documents, children=children,
                                  root=root, category=category)
            write_file(output_path, content)
            counter += 1

    for document in documents:
        _, file_name = path.split(document.file_path)
        output_path = path.join(output_dir, file_name)
        if document.is_markdown and markdown_template:
            output_path = re.sub(r'\.md$', '.html', output_path)

        if is_ready(output_path, category.modified_time):
            continue  # skip

        logger.info(f'updating {output_path}')
        if document.is_markdown and markdown_template:
            content = parse_jinja(markdown_template, documents=markdown_documents, children=children_with_html,
                                  root=root, document=document, category=category)
            write_file(output_path, content)
        elif document.is_html:
            content = parse_jinja(document.file_path, documents=markdown_documents, children=children_with_html,
                                  root=root, category=category)
            write_file(output_path, content)
        else:
            shutil.copy(document.file_path, output_path)
        counter += 1

    for child in children:
        _, child_dir = path.split(child.dir_path)
        counter += render_category(root, child, path.join(output_dir, child_dir))

    if counter > 0:
        logger.info(f'[{category.title}] update {counter} documents')

    return counter


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=str, default='dist',
                        help='')
    parser.add_argument('--version', '-v', action='store_true', default=False)
    parser.add_argument('--root-dir', type=str, required=True,
                        help='')

    args = parser.parse_args()

    if args.version:
        print('version: ', __version__)

    render_site(args.root_dir, args.output_dir)


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s %(levelname).1s %(name)s.%(filename)s %(lineno)d - %(message)s',
                        datefmt='%H:%M:%S',
                        level=logging.INFO)

    run()
