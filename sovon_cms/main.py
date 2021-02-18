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

MAX_INDEX = 999999

MARKDOWN_EXTENSIONS = ['markdown.extensions.extra',
                       # 'markdown.extensions.codehilite',
                       'markdown.extensions.tables',
                       'markdown.extensions.toc']

MARKDOWN_TEMPLATE = r'markdown.html'


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
    with open(file_path, 'w') as f:
        f.write(content)


def parse_markdown(file_path) -> str:
    s = read_file(file_path)
    r = md.markdown(s, extensions=MARKDOWN_EXTENSIONS)
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
    def __init__(self, dir_path, index=None, title=None):
        self.dir_path = dir_path

        if index is None and title is None:
            _dir, file_name = path.split(dir_path)
            self.index, self.title = parse_file_name(file_name)
        else:
            self.index = index
            self.title = title

        markdown_template = path.join(dir_path, MARKDOWN_TEMPLATE)
        self.markdown_template = markdown_template if path.exists(markdown_template) else None

    @property
    def documents(self) -> list:
        sub_dirs = [path.join(self.dir_path, p) for p in os.listdir(self.dir_path)]
        sub_dirs = filter(lambda p: path.isfile(p) and p != self.markdown_template, sub_dirs)

        return list(map(Document, sub_dirs))

    @property
    def children(self) -> list:
        sub_dirs = [path.join(self.dir_path, p) for p in os.listdir(self.dir_path)]
        sub_dirs = filter(path.isdir, sub_dirs)

        return list(map(Category, sub_dirs))

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(index={self.index}, title="{self.title}")'


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
    render_category(root, output_dir)
    logger.info('done')


def render_category(category: Category, output_dir: str):
    if not path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    children = category.children
    documents = category.documents
    markdown_template = category.markdown_template
    markdown_documents = [doc for doc in documents if doc.is_markdown]
    markdown_documents.sort(key=lambda doc: doc.index if doc.index is not None else MAX_INDEX)

    for document in documents:
        _, file_name = path.split(document.file_path)
        output_path = path.join(output_dir, file_name)
        if document.is_markdown and markdown_template:
            output_path = re.sub(r'\.md$', '.html', output_path)
            # content = md.markdown(document.content, extensions=MARKDOWN_EXTENSIONS)
            content = parse_jinja(markdown_template, documents=markdown_documents, children=children,
                                  document=document, category=category)
            write_file(output_path, content)
        elif document.is_html:
            content = parse_jinja(document.file_path, documents=markdown_documents, children=children,
                                  category=category)
            write_file(output_path, content)
        else:
            shutil.copy(document.file_path, output_path)

    for child in children:
        _, child_dir = path.split(child.dir_path)
        render_category(child, path.join(output_dir, child_dir))


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=str, default='dist',
                        help='')
    parser.add_argument('--version', '-v', action='store_true', default=False)
    parser.add_argument('--root-dir', type=str, default='.',
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
