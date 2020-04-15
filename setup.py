import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="bravia_tv", # Replace with your own username
    version="1.0.2",
    maintainer="David Nielsen",
    maintainer_email="dncielsen90@gmail.com",
    description="Python Bravia TV remote control",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/dcnielsen90/python-bravia-tv.git",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
