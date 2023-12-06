from setuptools import setup
from Cython.Build import cythonize

setup(
    name='ATMCopy',
    version='1.0.2',
    packages=[''],
    url='',
    license='',
    author='Efthimios G. Floros',
    author_email='xsystemgr@gmail.com',
    description=''
    ext_modules=cythonize("ATMCopyV2.py"),
)
