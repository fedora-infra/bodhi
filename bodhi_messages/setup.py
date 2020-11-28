import sys
import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(here, os.pardir))
from bodhi import _setuptools_config as base_setup  # noqa: E402

README = open('README.rst').read()

messages_setup = {
    'name': 'bodhi-messages',
    'description': 'JSON schema for messages sent by Bodhi',
    'long_description': README,
    'keywords': ["fedora", "fedora-messaging"],
    'packages': find_packages(),
    'include_package_data': True,
    'install_requires': ['bodhi', 'fedora_messaging'],
    'test_suite': 'tests',
    'entry_points': {
        "fedora.messages": [
            (
                "bodhi.buildroot_override.tag.v1="
                "bodhi_messages.schemas.buildroot_override:BuildrootOverrideTagV1"
            ),
            (
                "bodhi.buildroot_override.untag.v1="
                "bodhi_messages.schemas.buildroot_override:BuildrootOverrideUntagV1"
            ),
            "bodhi.errata.publish.v1=bodhi_messages.schemas.errata:ErrataPublishV1",
            "bodhi.compose.complete.v1=bodhi_messages.schemas.compose:ComposeCompleteV1",
            "bodhi.compose.composing.v1=bodhi_messages.schemas.compose:ComposeComposingV1",
            "bodhi.compose.start.v1=bodhi_messages.schemas.compose:ComposeStartV1",
            "bodhi.compose.sync.done.v1=bodhi_messages.schemas.compose:ComposeSyncDoneV1",
            "bodhi.compose.sync.wait.v1=bodhi_messages.schemas.compose:ComposeSyncWaitV1",
            "bodhi.repo.done.v1=bodhi_messages.schemas.compose:RepoDoneV1",
            "bodhi.update.comment.v1=bodhi_messages.schemas.update:UpdateCommentV1",
            (
                "bodhi.update.complete.stable.v1="
                "bodhi_messages.schemas.update:UpdateCompleteStableV1"
            ),
            (
                "bodhi.update.complete.testing.v1="
                "bodhi_messages.schemas.update:UpdateCompleteTestingV1"
            ),
            (
                "bodhi.update.status.testing.v1="
                "bodhi_messages.schemas.update:UpdateReadyForTestingV1"
            ),
            "bodhi.update.edit.v1=bodhi_messages.schemas.update:UpdateEditV1",
            "bodhi.update.eject.v1=bodhi_messages.schemas.update:UpdateEjectV1",
            "bodhi.update.karma.threshold.v1=bodhi_messages.schemas.update:UpdateKarmaThresholdV1",
            "bodhi.update.request.revoke.v1=bodhi_messages.schemas.update:UpdateRequestRevokeV1",
            "bodhi.update.request.stable.v1=bodhi_messages.schemas.update:UpdateRequestStableV1",
            "bodhi.update.request.testing.v1=bodhi_messages.schemas.update:UpdateRequestTestingV1",
            "bodhi.update.request.unpush.v1=bodhi_messages.schemas.update:UpdateRequestUnpushV1",
            (
                "bodhi.update.request.obsolete.v1="
                "bodhi_messages.schemas.update:UpdateRequestObsoleteV1"
            ),
            (
                "bodhi.update.requirements_met.stable.v1="
                "bodhi_messages.schemas.update:UpdateRequirementsMetStableV1"
            ),
        ]
    },
}

setup(**{**base_setup, **messages_setup})
