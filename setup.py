from setuptools import setup, find_packages

from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='billfred',
    version='0.2',

    description='A simple jabber bot',
    long_description=long_description,

    url='https://github.com/Ursoid/billfred3',
    author='Rulinux developers',
    license='MIT',

    packages=find_packages(exclude=['docs', 'tests']),
    install_requires=[
        'slixmpp',
        'feedparser',
        'aiosqlite',
        'aiohttp',
        'charset-normalizer',
    ],

    include_package_data=True,
    entry_points={
        'console_scripts': [
            'billfred=billfred:main',
        ],
    },
)
