import os
from setuptools import setup

with open(os.path.join(os.path.dirname(__file__), "README.md")) as file:
    long_description = file.read()

setup(
    name="OLG4P",
    version="0.1",
    url="https://github.com/yunline/OLG4P",
    description="Convert python script into python one-liner",
    long_description=long_description,
    long_description_content_type="text/markdown",
    py_modules=["oneliner"],
    author="yunline",
    license="MIT",
)
