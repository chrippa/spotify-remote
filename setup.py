#!/usr/bin/env python

from setuptools import setup

setup(name="spotify-remote",
      version="0.1.1",
      description="A simple CLI to control the Spotify desktop client.",
      author="Christopher Rosell",
      author_email="chrippa@tanuki.se",
      license="Simplified BSD",
      entry_points={
          "console_scripts": ["spotify-remote=spotify_remote:main"]
      },
      py_modules=["spotify_remote"],
      install_requires=["docopt", "requests"],
)

