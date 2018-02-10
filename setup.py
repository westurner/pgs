#!/usr/bin/env python
# -*- coding: utf-8 -*-

import codecs

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


with codecs.open('README.rst', encoding='UTF8') as readme_file:
    readme = readme_file.read()

with codecs.open('HISTORY.rst', encoding='UTF8') as history_file:
    history = history_file.read().replace('.. :changelog:', '')

requirements = [
    # TODO: put package requirements here
]

test_requirements = [
    # TODO: put package test requirements here
]

setup(
    name='pgs',
    version='0.1.4',
    description="A bottle webapp for serving static files from a git branch, or from the local filesystem.",
    long_description=readme + '\n\n' + history,
    author="Wes Turner",
    author_email='wes@wrd.nu',
    url='https://github.com/westurner/pgs',
    packages=[
        'pgs',
    ],
    package_dir={'pgs':
                 'pgs'},
    include_package_data=True,
    install_requires=requirements,
    license="BSD",
    zip_safe=False,
    keywords='pgs',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        "Programming Language :: Python :: 2",
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
    ],
    entry_points="""
    [console_scripts]
    pgs = pgs.app:main
    """,
    test_suite='tests',
    tests_require=test_requirements
)
