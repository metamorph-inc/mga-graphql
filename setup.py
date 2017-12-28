from setuptools import setup, find_packages

with open('README.rst') as f:
    readme = f.read()

with open('LICENSE') as f:
    license = f.read()

setup(
    name='mga-graphql',
    version='0.1.0',
    description='Utilities for making GraphQL queries against MGA',
    long_description=readme,
    author='Adam Nagel',
    author_email='adam.nagel+git@gmail.com',
    url='https://github.com/metamorph-inc/mga-graphql',
    license=license,
    packages=find_packages(exclude=('tests', 'docs')),
    install_requires=[
        'Flask',
        'Flask-GraphQL',
        'graphene',
        'graphql-core',
        'graphql-relay'
    ]
)
