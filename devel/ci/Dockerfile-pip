FROM registry.fedoraproject.org/fedora:29
LABEL maintainer="Randy Barlow <bowlofeggs@fedoraproject.org>"

# This works around https://bugzilla.redhat.com/show_bug.cgi?id=1705265
RUN dnf install -y dnf-plugin-ovl

# The echo works around https://bugzilla.redhat.com/show_bug.cgi?id=1483553 and any other future dnf
# upgrade bugs.
RUN dnf upgrade -y || echo "We are not trying to test dnf upgrade, so ignoring dnf failure."
RUN dnf install -y \
    createrepo_c \
    findutils \
    git \
    python3-createrepo_c \
    python3-koji \
    createrepo_c \
    gcc \
    gcc-c++ \
    graphviz \
    make \
    postgresql-devel \
    python3-devel \
    python3-librepo \
    python3-simplemediawiki \
    redhat-rpm-config \
    python3-libcomps

COPY requirements.txt /bodhi/requirements.txt

RUN pip-3 install -r /bodhi/requirements.txt
RUN pip-3 install \
    alembic \
    cornice_sphinx \
    diff-cover \
    flake8 \
    flake8-import-order \
    responses \
    pydocstyle \
    pytest \
    pytest-cov \
    "sphinx<2.1" \
    sqlalchemy_schemadisplay \
    webtest

# Fake pungi being installed so we can avoid it and all its dependencies
RUN ln -s /usr/bin/true /usr/bin/pungi-koji
VOLUME ["/results"]
WORKDIR /bodhi
CMD ["bash"]
COPY . /bodhi
RUN sed -i '/pyramid_debugtoolbar/d' setup.py
RUN sed -i '/pyramid_debugtoolbar/d' devel/development.ini.example
# The Makefile is set to use sphinx-build-3, but the pip installed sphinx is just called
# sphinx-build.
RUN sed -i 's/sphinx-build-3/sphinx-build/' docs/Makefile
RUN cp devel/development.ini.example development.ini
