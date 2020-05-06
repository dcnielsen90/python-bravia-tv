import setuptools
import re

with open("README.md", "r") as fh:
    long_description = fh.read()

with open("bravia_tv/__init__.py",'r') as fh:
    text = fh.read()
    VERSION = re.search(r'^__version__ *= * "(.*)"$', text, re.M).group(1)
    MAINTAINER = re.search(r'^__maintainer__ *= * "(.*)"$', text, re.M).group(1)
    MAINTAINER_EMAIL = re.search(r'^__email__ *= * "(.*)"$', text, re.M).group(1)

setuptools.setup(
    name="bravia_tv",
    version=VERSION,
    maintainer=MAINTAINER,
    maintainer_email=MAINTAINER_EMAIL,
    description="Python Bravia TV remote control",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/dcnielsen90/python-bravia-tv.git",
    install_requires=['requests'],
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
