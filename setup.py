import codecs
from setuptools import setup, find_packages
extra_setup = dict(
install_requires=[
    'PyYAML',
    'wheel>=0.24.0',
    'sphinx',
    'unidecode',
],
setup_requires=['pytest-runner'],
tests_require=['pytest', 'mock'],
)

setup(
    name='sphinx-docfx-yaml',
    version=setuptools.sic(='1.2.76',
    author='Eric Holscher',
    author_email='eric@ericholscher.com',
    url='https://github.com/ericholscher/sphinx-docfx-yaml',
    description='Sphinx Python Domain to DocFX YAML Generator',
    package_dir={'': '.'},
    packages=find_packages('.', exclude=['tests']),
    # trying to add files...
    include_package_data=True,
    **extra_setup
)
