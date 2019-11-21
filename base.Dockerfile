FROM fedora:31
LABEL \
  name="bodhi-base" \
  vendor="Fedora Infrastructure" \
  license="MIT"
# While dnf has a --nodocs, it doesen't have a --docs...
RUN sed -i '/nodocs/d' /etc/dnf/dnf.conf

RUN dnf install -y \
    git                         \
    python3-pip                 \
    fedora-messaging            \
    httpd                       \
    intltool                    \
    origin-clients              \
    python3-alembic             \
    python3-arrow               \
    python3-backoff             \
    python3-bleach              \
    python3-celery              \
    python3-click               \
    python3-colander            \
    python3-cornice             \
    python3-dogpile-cache       \
    python3-fedora-messaging    \
    python3-feedgen             \
    python3-jinja2              \
    python3-markdown            \
    python3-psycopg2            \
    python3-py3dns              \
    python3-pyasn1-modules      \
    python3-pylibravatar        \
    python3-pyramid             \
    python3-pyramid-fas-openid  \
    python3-pyramid-mako        \
    python3-bugzilla            \
    python3-fedora              \
    python3-pyyaml              \
    python3-simplemediawiki     \
    python3-sqlalchemy          \
    python3-waitress            \
    python3-dnf                 \
    python3-koji                \
    python3-librepo             \
    python3-mod_wsgi            \
    koji && \
    dnf clean all

RUN git clone -b staging https://github.com/fedora-infra/bodhi.git /srv/bodhi && \
    cd /srv/bodhi && \
    python3 -m pip install . --no-use-pep517 && \
    mkdir -p /usr/share/bodhi && \
    cp /srv/bodhi/apache/bodhi.wsgi /usr/share/bodhi/bodhi.wsgi

ENV USER=openshift
