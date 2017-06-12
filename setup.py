from setuptools import setup, find_packages

from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='billfred',
    version='0.1',

    description='A simple jabber bot',
    long_description=long_description,

    url='https://github.com/Ursoid/billfred3',
    author='Rulinux developers',
    # Choose your license
    license='MIT',

    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],

    packages=find_packages(exclude=['contrib', 'docs', 'tests']),
    install_requires=[
        'sleekxmpp'
    ],

    include_package_data=True,
    entry_points={
        'console_scripts': [
            'billfred=billfred.main:main',
        ],
    },
)
