from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

with open('requirements.txt') as f:
    required = f.read().splitlines()

setup(
    name='chatter',
    version='0.1.0',
    author="Ian Straub",
    author_email="istraub@goldentoadsoftware.com",
    description="A set of tools for analyzing trending news articles on Twitter",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/rji-futures-lab/Chatter",
    packages=find_packages(include=['chatter', 'chatter.*']),
    python_requires='>=3.7',
    install_requires=required,
    entry_points={
        'console_scripts': ['chatter=chatter.cli:main']
    },
    package_data={'chatter':['config/config.yaml']},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
