# Copyright © 2011-2019 Red Hat, Inc. and others.
#
# This file is part of Bodhi.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""Initialize Bodhi's models."""

from sqlalchemy import event

from .enums import (   # noqa : 401
    EnumSymbol, EnumMeta, DeclEnum, DeclEnumType,
    ContentType, UpdateStatus, TestGatingStatus, UpdateType, UpdateRequest,
    UpdateSeverity, UpdateSuggestion, ReleaseState, ComposeState, PackageManager)
from .bodhibase import BodhiBase, Base, metadata  # noqa : 401
from .testcase import TestCase  # noqa : 401
from .build import Build, ContainerBuild, FlatpakBuild, ModuleBuild, RpmBuild  # noqa : 401
from .package import Package, ContainerPackage, FlatpakPackage, ModulePackage, RpmPackage  # noqa : 401
from .comment import BugKarma, Comment, TestCaseKarma  # noqa : 401
from .release import Release  # noqa : 401
from .update import Update
from .bug import Bug  # noqa : 401
from .user import User, Group  # noqa : 401
from .compose import Compose
from .override import BuildrootOverride  # noqa : 401

event.listen(
    Compose.state,
    'set',
    Compose.update_state_date,
    active_history=True
)

event.listen(
    Update.test_gating_status,
    'set',
    Update.comment_on_test_gating_status_change,
    active_history=True,
    raw=True,
)

event.listen(
    Update.status,
    'set',
    Update._ready_for_testing,
    active_history=True,
)
