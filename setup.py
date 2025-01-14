"""
Setup configuration for JustDownloadIt package.

This module contains the setup configuration for installing JustDownloadIt.
It specifies package metadata, dependencies, and installation requirements.

Dependencies:
    - customtkinter: Modern themed tkinter widgets
    - pytube: YouTube download library
    - pySmartDL: Smart download library
"""

from setuptools import setup, find_packages

setup(
    name="JustDownloadIt",
    version="0.1.0",
    packages=find_packages(),
    package_dir={'': '.'},
    install_requires=[
        'customtkinter',
        'pytube',
        'pySmartDL',
    ],
)
