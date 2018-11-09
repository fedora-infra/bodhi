FROM registry.fedoraproject.org/fedora:29
LABEL \
  name="bodhi-web" \
  vendor="Fedora Infrastructure" \
  maintainer="Aurelien Bompard <abompard@fedoraproject.org>" \
  license="MIT"

RUN curl -o /etc/yum.repos.d/infra-tags.repo https://infrastructure.fedoraproject.org/cgit/ansible.git/plain/files/common/fedora-infra-tags.repo

# While dnf has a --nodocs, it doesen't have a --docs...
RUN sed -i '/nodocs/d' /etc/dnf/dnf.conf

# Install Bodhi deps
# 1. bodhi-server
# 2. bodhi-composer
# 3. python3-bodhi-client
RUN dnf install -y \
    \
    httpd \
    intltool \
    liberation-mono-fonts \
    python3-dogpile-cache \
    python3-koji \
    python3-librepo \
    python3-mod_wsgi \
    python3-pillow \
    "python3dist(alembic)" \
    "python3dist(arrow)" \
    "python3dist(bleach)" \
    "python3dist(click)" \
    "python3dist(colander)" \
    "python3dist(cornice)" \
    "python3dist(cryptography)" \
    "python3dist(fedmsg)" \
    "python3dist(feedgen)" \
    "python3dist(jinja2)" \
    "python3dist(kitchen)" \
    "python3dist(markdown)" \
    "python3dist(psycopg2)" \
    "python3dist(pylibravatar)" \
    "python3dist(pyramid)" \
    "python3dist(pyramid-fas-openid)" \
    "python3dist(pyramid-mako)" \
    "python3dist(python-bugzilla)" \
    "python3dist(python-fedora)" \
    "python3dist(python3-openid)" \
    "python3dist(simplemediawiki)" \
    "python3dist(six)" \
    "python3dist(sqlalchemy)" \
    "python3dist(waitress)" \
    \
    python3-createrepo_c \
    python3-hawkey \
    skopeo \
    \
    /usr/bin/koji \
    python3-dnf \
    python3-koji \
    "python3dist(click)" \
    "python3dist(iniparse)" \
    "python3dist(kitchen)" \
    "python3dist(python-fedora)" \
    "python3dist(six)" \
    \
    fedmsg \
    fedmsg-base \
    git

# Create bodhi user
RUN groupadd -r bodhi && \
    useradd  -r -s /sbin/nologin -d /home/bodhi/ -m -c 'Bodhi Server' -g bodhi bodhi

# Copy source
WORKDIR /bodhi
COPY . /bodhi

# Install it
RUN sed -i -e '/pyramid_debugtoolbar/d' setup.py devel/development.ini.example
RUN python3 setup.py build && pip3 install .

# Configuration
RUN mkdir -p /etc/bodhi
COPY production.ini /etc/bodhi/production.ini

COPY devel/ci/integration/bodhi/start.sh /etc/bodhi/start.sh
COPY devel/ci/integration/bodhi/httpd.conf /etc/bodhi/httpd.conf
COPY apache/bodhi.wsgi /etc/bodhi/bodhi.wsgi
RUN sed -i -e 's,/var/www,/httpdir,g' /etc/bodhi/bodhi.wsgi
# Put the fedmsg config in place. Let's name it starting with zz so it sorts last.
COPY devel/ci/integration/bodhi/fedmsg.py /etc/fedmsg.d/zzbodhi.py

RUN \
# Put the fedmsg cert and key in place
    mkdir -p /etc/pki/fedmsg/ && \
    ln -sf /etc/pki/fedmsg/key/fedmsg-bodhi.key /etc/pki/fedmsg/bodhi.key && \
    ln -sf /etc/pki/fedmsg/crt/fedmsg-bodhi.crt /etc/pki/fedmsg/bodhi.crt && \
# Set up krb5
    rm -f /etc/krb5.conf && \
    ln -sf /etc/bodhi/krb5.conf /etc/krb5.conf && \
    ln -sf /etc/keytabs/koji-keytab /etc/krb5.bodhi_bodhi.fedoraproject.org.keytab

# Apache
RUN mkdir -p /httpdir && chown bodhi:bodhi /httpdir

EXPOSE 8080
USER bodhi
ENV USER=bodhi
CMD ["bash", "/etc/bodhi/start.sh"]
