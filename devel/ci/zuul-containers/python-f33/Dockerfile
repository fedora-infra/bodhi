# Copyright (C) 2020 Red Hat
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# This file is maintained with the ../containers.dhall configuration

FROM registry.fedoraproject.org/fedora:33
ENV HOME=/workspace
ENV XDG_CACHE_HOME=/workspace/.cache
ENV PATH=/workspace/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# OpenShift container might run as any user, so we need to make sure the workspace is writable:
# https://docs.openshift.com/container-platform/4.2/openshift_images/create-images.html#images-create-guide-openshift_create-images
WORKDIR /workspace
RUN mkdir -p /workspace/.local && chgrp -R 0 /workspace && chmod -R g=u /workspace

RUN dnf update -y && dnf install -y iproute rsync git traceroute unzip bzip2 make curl wget tar procps-ng which sudo unzip findutils grep ncurses-devel openssl-devel zlib-devel krb5-devel python3-mypy python3-flake8 python3-pyyaml python3-tox python3-prometheus_client python3-cliff python3-pbr python3-systemd python3-devel twine python3-setuptools python2-setuptools python3 python3-devel python3-wheel python3-pip python3-sphinx python3-sphinx_rtd_theme && dnf clean all

RUN curl -OL https://github.com/dhall-lang/dhall-haskell/releases/download/1.30.0/dhall-1.30.0-x86_64-linux.tar.bz2 && echo '6845421de9c3cc40f4140a1278c408df8ef49bf8086ee7f37730d2eda8ce9402  dhall-1.30.0-x86_64-linux.tar.bz2' | sha256sum -c && tar -xf dhall-1.30.0-x86_64-linux.tar.bz2 --strip-components=2 -j --mode='a+x' -C /usr/bin && rm dhall-1.30.0-x86_64-linux.tar.bz2

# This run create a sudo configuration so that when a container running as root delete /etc/sudoers.d/zuul,
# then it can no longer run sudo, satisfying the revoke-sudo zuul jobs role.
RUN echo 'zuul:x:0:0:root:/workspace:/bin/bash' >> /etc/passwd && mv /etc/sudoers /etc/sudoers.d/zuul && grep includedir /etc/sudoers.d/zuul > /etc/sudoers && sed -e 's/.*includedir.*//' -i /etc/sudoers.d/zuul && chmod 440 /etc/sudoers
# Workaround for k1s
RUN ln -s /workspace/src /root/src && ln -s /workspace/.local /root/.local
