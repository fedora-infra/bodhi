#!/usr/bin/bash -ex
# Copyright (c) 2017-2018 Red Hat, Inc.
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

# This script is used to run the tests in the CI infrastructure, and launches a variety of parallel
# containers to test Bodhi across supported Fedora releases.


sudo yum install -y epel-release
sudo yum install -y bzip2 docker parallel python34-click

sudo systemctl start docker

./devel/ci/bodhi-ci $@
