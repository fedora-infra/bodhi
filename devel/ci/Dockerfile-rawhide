FROM registry.fedoraproject.org/fedora:rawhide
LABEL maintainer="Randy Barlow <bowlofeggs@fedoraproject.org>"

RUN dnf upgrade -y
RUN dnf install --disablerepo rawhide-modular -y \
    createrepo_c \
    fedora-messaging \
    findutils \
    git \
    make \
    python3-alembic \
    python3-arrow \
    python3-backoff \
    python3-bleach \
    python3-bugzilla \
    python3-click \
    python3-colander \
    python3-cornice \
    python3-cornice-sphinx \
    python3-createrepo_c \
    python3-diff-cover \
    python3-dnf \
    python3-dogpile-cache \
    python3-fedora \
    python3-feedgen \
    python3-jinja2 \
    python3-koji \
    python3-libcomps \
    python3-librepo \
    python3-markdown \
    python3-munch \
    python3-openid \
    python3-psycopg2 \
    python3-pylibravatar \
    python3-pyramid \
    python3-pyramid-fas-openid \
    python3-pyramid-mako \
    python3-pytest \
    python3-pytest-cov \
    python3-responses \
    python3-simplemediawiki \
    python3-sqlalchemy \
    python3-sqlalchemy_schemadisplay \
    python3-waitress \
    python3-webtest \
    python3-yaml

# Fake pungi being installed so we can avoid it and all its dependencies
RUN ln -s /usr/bin/true /usr/bin/pungi-koji
VOLUME ["/results"]
WORKDIR /bodhi
CMD ["bash"]
COPY . /bodhi
RUN sed -i '/pyramid_debugtoolbar/d' setup.py
RUN sed -i '/pyramid_debugtoolbar/d' devel/development.ini.example
RUN cp devel/development.ini.example development.ini
