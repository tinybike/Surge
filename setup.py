#!/usr/bin/env python
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

setup(
    name="surge",
    version="0.1",
    description="Cryptocurrency market data downloader",
    author="Jack Peterson",
    author_email="<jack@tinybike.net>",
    maintainer="Jack Peterson",
    maintainer_email="<jack@tinybike.net>",
    license="MIT",
    url="https://github.com/tensorjack/surge",
    download_url = 'https://github.com/tensorjack/surge/tarball/0.1',
    packages=["surge"],
    install_requires=["psycopg2", "requests"],
    keywords = ["bitcoin", "download", "altcoin", "data", "analytics"]
)
