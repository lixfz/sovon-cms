# -*- coding:utf-8 -*-

from __future__ import absolute_import

from setuptools import find_packages
from setuptools import setup

import sovon_cms

name = sovon_cms.__name__.replace('_', '-')
version = sovon_cms.__version__

print(f'setup {name}:{version}')


def read_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def read_requirements(file_path='requirements.txt'):
    import os

    if not os.path.exists(file_path):
        return []

    with open(file_path, 'r')as f:
        lines = f.readlines()

    lines = [x.strip('\n').strip(' ') for x in lines]
    lines = list(filter(lambda x: len(x) > 0 and not x.startswith('#'), lines))

    return lines


def read_extra_requirements():
    import glob
    import re

    extra = {}

    for file_name in glob.glob('requirements-*.txt'):
        key = re.search('requirements-(.+).txt', file_name).group(1)
        req = read_requirements(file_name)
        if req:
            extra[key] = req

    if extra and 'all' not in extra.keys():
        extra['all'] = sorted({v for req in extra.values() for v in req})

    return extra


MIN_PYTHON_VERSION = '>=3.6.*'

long_description = read_file('README.md')
requires = read_requirements()
extras_require = read_extra_requirements()

setup(
    name=name,
    version=version,
    description='A simple content management system to generate static web site'
                ' from markdown documents and jinja templates.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/lixfz/sovon-cms',
    author='SOVON.NET',
    author_email='about@sovon.net',
    license='Apache License 2.0',
    install_requires=requires,
    python_requires=MIN_PYTHON_VERSION,
    extras_require=extras_require,
    classifiers=[
        'Operating System :: OS Independent',
        'Intended Audience :: Developers',
        'Intended Audience :: Education',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Topic :: Software Development',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    packages=find_packages(exclude=('docs', 'tests')),
    package_data={
        # nothing
    },
    zip_safe=False,
    include_package_data=True,
    entry_points={
        'console_scripts': [
            f'{name} = {sovon_cms.__name__}.main:run',
        ]
    },
)
