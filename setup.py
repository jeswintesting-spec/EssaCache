from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="essacache",
    version="1.0.0",
    author="Jeswin",
    description="A blazing-fast, in-memory data structure store used as a cache (Redis Clone in Python)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    install_requires=[
        "prompt_toolkit>=3.0.0",
        "rich>=10.0.0",
        "prometheus-client>=0.20.0"
    ],
    scripts=["essacli.py"],
    entry_points={
        "console_scripts": [
            "essacache-server=essacache.__main__:main",
        ]
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.8',
)
