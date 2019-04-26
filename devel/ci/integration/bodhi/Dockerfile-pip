FROM bodhi-ci/pip
LABEL \
  name="bodhi-web" \
  vendor="Fedora Infrastructure" \
  maintainer="Aurelien Bompard <abompard@fedoraproject.org>" \
  license="MIT"

# For integration testing we're using the infrastructure repo
RUN curl -o /etc/yum.repos.d/infra-tags.repo https://infrastructure.fedoraproject.org/cgit/ansible.git/plain/files/common/fedora-infra-tags.repo
RUN dnf upgrade -y

# Install Bodhi deps (that were not needed by the unittests container)
RUN dnf install -y \
    httpd \
    intltool \
    python3-koji \
    /usr/bin/koji \
    python3-mod_wsgi \
    python3-dnf \
    skopeo

# Mimic RPM's handling of Python3-specific binaries
RUN ln -s alembic /usr/local/bin/alembic-3

# Create bodhi user
RUN groupadd -r bodhi && \
    useradd  -r -s /sbin/nologin -d /home/bodhi/ -m -c 'Bodhi Server' -g bodhi bodhi

# Install it
RUN python3 setup.py build && pip3 install .

# Configuration
RUN mkdir -p /etc/bodhi
COPY production.ini /etc/bodhi/production.ini

COPY devel/ci/integration/bodhi/start.sh /etc/bodhi/start.sh
COPY devel/ci/integration/bodhi/fedora-messaging.toml /etc/fedora-messaging/config.toml
COPY devel/ci/integration/bodhi/httpd.conf /etc/bodhi/httpd.conf
COPY apache/bodhi.wsgi /etc/bodhi/bodhi.wsgi
RUN sed -i -e 's,/var/www,/httpdir,g' /etc/bodhi/bodhi.wsgi

RUN \
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
