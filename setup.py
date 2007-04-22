# $Id: $

from setuptools import setup, find_packages
from turbogears.finddata import find_package_data

setup(
    name="bodhi",
    version="1.0",
    description="",
    author="Luke Macken",
    author_email="lmacken@fedoraproject.org",
    url="https://hosted.fedoraproject.org/projects/bodhi",
    license="GPL",

    install_requires = [
        "TurboGears >= 1.0.1",
    ],
    scripts = ["start-bodhi.py"],
    zip_safe=False,
    packages=find_packages(),
    package_data = find_package_data(where='bodhi',
                                     package='bodhi'),
    keywords = ['turbogears.app'],
    classifiers = [
        'Development Status :: 3 - Alpha',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Framework :: TurboGears',
    ],
    test_suite = 'nose.collector',
)
