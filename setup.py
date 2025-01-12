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
