FROM registry.fedoraproject.org/fedora:29
LABEL maintainer="Randy Barlow <bowlofeggs@fedoraproject.org>"

# The echo works around https://bugzilla.redhat.com/show_bug.cgi?id=1483553 and any other future dnf
# upgrade bugs.
RUN dnf upgrade -y || echo "We are not trying to test dnf upgrade, so ignoring dnf failure."
RUN dnf install --disablerepo rawhide-modular -y \
    createrepo_c \
    fedora-messaging \
    findutils \
    git \
    python3-bugzilla \
    python3-createrepo_c \
    python3-koji \
    make \
    python3-alembic \
    python3-arrow \
    python3-backoff \
    python3-bleach \
    python3-click \
    python3-colander \
    python3-diff-cover \
    python3-dogpile-cache \
    python3-fedora \
    python3-feedgen \
    python3-jinja2 \
    python3-libcomps \
    python3-librepo \
    python3-markdown \
    python3-munch \
    python3-openid \
    python3-psycopg2 \
    python3-pylibravatar \
    python3-pyramid \
    python3-pyramid-mako \
    python3-pytest \
    python3-pytest-cov \
    python3-pyyaml \
    python3-responses \
    python3-simplemediawiki \
    python3-sqlalchemy \
    python3-webtest \
    python3-cornice \
    python3-cornice-sphinx \
    python3-pyramid-fas-openid

# sqlalchemy_schemadisplay is not packaged for Python 3 in Fedora < 30
RUN pip-3 install sqlalchemy_schemadisplay

# Fake pungi being installed so we can avoid it and all its dependencies
RUN ln -s /usr/bin/true /usr/bin/pungi-koji
VOLUME ["/results"]
WORKDIR /bodhi
CMD ["bash"]
COPY . /bodhi
RUN sed -i '/pyramid_debugtoolbar/d' setup.py
RUN sed -i '/pyramid_debugtoolbar/d' devel/development.ini.example
RUN cp devel/development.ini.example development.ini
