#!/usr/bin/env python3
"""
Setup configuration for netucs package
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="netucs",
    version="1.0.0",
    author="Fabrizio Pollastri",
    author_email="f.pollastri@inrim.it",
    description="Network UDP Client Server data exchange - asynchronous client/server UDP communication",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/f-pollastri/netucs",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Topic :: Communications",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    keywords="udp client server asyncio network communication data-exchange",
    project_urls={
        "Bug Reports": "https://github.com/f-pollastri/netucs/issues",
        "Source": "https://github.com/f-pollastri/netucs",
    },
)
