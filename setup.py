import os
import re

from setuptools import setup, find_packages
import setuptools.command.egg_info


def get_requirements(requirements_file='requirements.txt'):
    """
    Get the contents of a file listing the requirements.

    Args:
        requirements_file (str): path to a requirements file

    Returns:
        list: the list of requirements, or an empty list if
              `requirements_file` could not be opened or read
    """
    lines = open(requirements_file).readlines()
    dependencies = []
    for line in lines:
        maybe_dep = line.strip()
        if maybe_dep.startswith('#'):
            # Skip pure comment lines
            continue
        if maybe_dep.startswith('git+'):
            # VCS reference for dev purposes, expect a trailing comment
            # with the normal requirement
            __, __, maybe_dep = maybe_dep.rpartition('#')
        else:
            # Ignore any trailing comment
            maybe_dep, __, __ = maybe_dep.partition('#')
        # Remove any whitespace and assume non-empty results are dependencies
        maybe_dep = maybe_dep.strip()
        if maybe_dep:
            dependencies.append(maybe_dep)
    return dependencies


here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.rst')).read()
VERSION = '5.2.0'


# Possible options are at https://pypi.python.org/pypi?%3Aaction=list_classifiers
CLASSIFIERS = [
    'Development Status :: 5 - Production/Stable',
    'Intended Audience :: Developers',
    'Intended Audience :: System Administrators',
    'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
    'Operating System :: POSIX :: Linux',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.6',
    'Programming Language :: Python :: 3.7',
    'Topic :: System :: Software Distribution']
LICENSE = 'GPLv2+'
MAINTAINER = 'Fedora Infrastructure Team'
MAINTAINER_EMAIL = 'infrastructure@lists.fedoraproject.org'
PLATFORMS = ['Fedora', 'GNU/Linux']
URL = 'https://github.com/fedora-infra/bodhi'


setuptools.command.egg_info.manifest_maker.template = 'BODHI_MANIFEST.in'


setup(
    name='bodhi',
    version=VERSION,
    description='bodhi common package',
    long_description=README,
    classifiers=CLASSIFIERS,
    license=LICENSE,
    maintainer=MAINTAINER,
    maintainer_email=MAINTAINER_EMAIL,
    platforms=PLATFORMS,
    url=URL,
    keywords='fedora',
    packages=['bodhi'],
    include_package_data=True,
    zip_safe=False,
    install_requires=[],
    tests_require=[
        'flake8',
        'pytest',
        'pytest-cov',
        'webtest',
        'conu >= 0.5.0',
        'munch',
        'psycopg2',
        'requests',
    ],
)


setuptools.command.egg_info.manifest_maker.template = 'CLIENT_MANIFEST.in'


setup(
    name='bodhi-client',
    version=VERSION,
    description='bodhi client',
    long_description=README,
    classifiers=CLASSIFIERS,
    license=LICENSE,
    maintainer=MAINTAINER,
    maintainer_email=MAINTAINER_EMAIL,
    platforms=PLATFORMS,
    url=URL,
    keywords='fedora',
    packages=['bodhi.client'],
    include_package_data=False,
    zip_safe=False,
    install_requires=['click', 'python-fedora >= 0.9.0'],
    entry_points="""\
    [console_scripts]
    bodhi = bodhi.client:cli
    """)


setuptools.command.egg_info.manifest_maker.template = 'MESSAGES_MANIFEST.in'


setup(
    name="bodhi-messages",
    version=VERSION,
    description="JSON schema for messages sent by Bodhi",
    long_description=('Bodhi Messages\n==============\n\n This package contains the schema for '
                      'messages published by Bodhi.'),
    url="https://github.com/fedora-infra/bodhi/",
    # Possible options are at https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        "License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
    ],
    license="GPLv2+",
    maintainer="Fedora Infrastructure Team",
    maintainer_email="infrastructure@lists.fedoraproject.org",
    platforms=["Fedora", "GNU/Linux"],
    keywords=["fedora", "fedora-messaging"],
    packages=find_packages(
        exclude=['bodhi.client', 'bodhi.client.*', 'bodhi.server', 'bodhi.server.*', 'bodhi.tests',
                 'bodhi.tests.*']),
    include_package_data=True,
    zip_safe=False,
    install_requires=["fedora_messaging"],
    test_suite="bodhi.tests.messages",
    entry_points={
        "fedora.messages": [
            (
                "bodhi.buildroot_override.tag.v1="
                "bodhi.messages.schemas.buildroot_override:BuildrootOverrideTagV1"
            ), (
                "bodhi.buildroot_override.untag.v1="
                "bodhi.messages.schemas.buildroot_override:BuildrootOverrideUntagV1"
            ),
            "bodhi.errata.publish.v1=bodhi.messages.schemas.errata:ErrataPublishV1",
            "bodhi.compose.complete.v1=bodhi.messages.schemas.compose:ComposeCompleteV1",
            "bodhi.compose.composing.v1=bodhi.messages.schemas.compose:ComposeComposingV1",
            "bodhi.compose.start.v1=bodhi.messages.schemas.compose:ComposeStartV1",
            "bodhi.compose.sync.done.v1=bodhi.messages.schemas.compose:ComposeSyncDoneV1",
            "bodhi.compose.sync.wait.v1=bodhi.messages.schemas.compose:ComposeSyncWaitV1",
            "bodhi.repo.done.v1=bodhi.messages.schemas.compose:RepoDoneV1",
            "bodhi.update.comment.v1=bodhi.messages.schemas.update:UpdateCommentV1",
            (
                "bodhi.update.complete.stable.v1="
                "bodhi.messages.schemas.update:UpdateCompleteStableV1"
            ),
            (
                "bodhi.update.complete.testing.v1="
                "bodhi.messages.schemas.update:UpdateCompleteTestingV1"
            ),
            (
                "bodhi.update.status.testing.v1="
                "bodhi.messages.schemas.update:UpdateReadyForTestingV1"
            ),
            "bodhi.update.edit.v1=bodhi.messages.schemas.update:UpdateEditV1",
            "bodhi.update.eject.v1=bodhi.messages.schemas.update:UpdateEjectV1",
            "bodhi.update.karma.threshold.v1=bodhi.messages.schemas.update:UpdateKarmaThresholdV1",
            "bodhi.update.request.revoke.v1=bodhi.messages.schemas.update:UpdateRequestRevokeV1",
            "bodhi.update.request.stable.v1=bodhi.messages.schemas.update:UpdateRequestStableV1",
            "bodhi.update.request.testing.v1=bodhi.messages.schemas.update:UpdateRequestTestingV1",
            "bodhi.update.request.unpush.v1=bodhi.messages.schemas.update:UpdateRequestUnpushV1",
            (
                "bodhi.update.request.obsolete.v1="
                "bodhi.messages.schemas.update:UpdateRequestObsoleteV1"
            ), (
                "bodhi.update.requirements_met.stable.v1="
                "bodhi.messages.schemas.update:UpdateRequirementsMetStableV1"
            ),
        ]
    },
)


setuptools.command.egg_info.manifest_maker.template = 'SERVER_MANIFEST.in'
# Due to https://github.com/pypa/setuptools/issues/808, we need to include the bodhi superpackage
# and then remove it if we want find_packages() to find the bodhi.server package and its
# subpackages without including the bodhi top level package.
server_packages = find_packages(
    exclude=['bodhi.client', 'bodhi.client.*', 'bodhi.messages', 'bodhi.messages.*', 'bodhi.tests',
             'bodhi.tests.*'])
server_packages.remove('bodhi')


setup(
    name='bodhi-server',
    version=VERSION,
    description='bodhi server',
    long_description=README,
    classifiers=CLASSIFIERS + [
        'Framework :: Pyramid',
        'Programming Language :: JavaScript',
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application"],
    license=LICENSE,
    maintainer=MAINTAINER,
    maintainer_email=MAINTAINER_EMAIL,
    platforms=PLATFORMS,
    url=URL,
    keywords='web fedora pyramid',
    packages=server_packages,
    include_package_data=True,
    zip_safe=False,
    install_requires=get_requirements(),
    message_extractors={'.': []},
    entry_points="""\
    [paste.app_factory]
    main = bodhi.server:main
    [console_scripts]
    initialize_bodhi_db = bodhi.server.scripts.initializedb:main
    bodhi-push = bodhi.server.push:push
    bodhi-untag-branched = bodhi.server.scripts.untag_branched:main
    bodhi-skopeo-lite = bodhi.server.scripts.skopeo_lite:main
    bodhi-sar = bodhi.server.scripts.sar:get_user_data
    bodhi-shell = bodhi.server.scripts.bshell:get_bodhi_shell
    bodhi-clean-old-composes = bodhi.server.scripts.compat:clean_old_composes
    bodhi-expire-overrides = bodhi.server.scripts.compat:expire_overrides
    bodhi-approve-testing = bodhi.server.scripts.compat:approve_testing
    bodhi-check-policies = bodhi.server.scripts.compat:check_policies
    """,
    paster_plugins=['pyramid'])
