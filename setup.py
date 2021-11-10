#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import setup, find_packages

with open('README.md') as readme_file:
    readme = readme_file.read()

requirements = [
    'mergedeep >= 1.3.4',
    'ccxt == 1.49.61',
    'aiounittest >= 1.4.1'
]

setup(
    author="Jan Silhan",
    author_email='silhan.it@gmail.com',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    description="General purpose library for execution of atomic trades",
    install_requires=requirements,
    license="MIT license",
    long_description=readme,
    include_package_data=True,
    keywords='atomic-trades',
    name='atomic-trades',
    packages=find_packages(include=['atomic_trades']),
    url='https://github.com/jsilhan/atomic-trades',
    version='0.1.0',
    zip_safe=False,
)
