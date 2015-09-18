#!/usr/bin/env python

from setuptools import setup


setup(
    name='multisig-recovery',
    version = '0.1',
    packages=[
        'multisigrecovery',
        'tests'
    ],
    license='http://opensource.org/licenses/BSD-2-Clause',
    author='Tom James Holub (https://github.com/tomholu)',
    url='https://github.com/bit-oasis/multisig-recovery',
    description='Branch migrations for multisig wallets',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Topic :: Internet',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    install_requires=[
        'pycoin',
        'multisig-core'
    ],
)
