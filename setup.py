from setuptools import setup, find_packages

extras_require = dict()
extras_require['dev'] = [
    'black',
    'flake8',
    'isort',
]

extras_require['test'] = [
    'pytest',
]

extras_require['ci'] = [
    *extras_require['test'],
    'pytest-cov',
]

setup(
    name="isabelle_lsp_client",
    version="0.0.1",
    description="A Language Server Protocol client for Isabelle written in Python",
    long_description=open("README.rst").read(),
    long_description_content_type="text/x-rst",
    author="Christian Kissig",
    url="https://github.com/christiankissig/python-isabelle-lsp-client",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    install_requires=[
        "pydantic>=2.9.0",
        "lsp_client>=0.0.2",
    ],
    extras_require=extras_require,
    entry_points={
        'console_scripts': [
            'flake8 = flake8.main.cli:main',
        ],
    },
)
