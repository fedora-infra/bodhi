FROM fedora:29
LABEL \
  name="resultsdb" \
  vendor="Fedora Infrastructure" \
  maintainer="Aurelien Bompard <abompard@fedoraproject.org>" \
  license="MIT"

# Install deps
RUN dnf install -y \
    httpd \
    python3-mod_wsgi \
    resultsdb \
    python3-psycopg2 \
    python3-fedora-messaging

# Configuration
COPY devel/ci/integration/resultsdb/settings.py /etc/resultsdb/settings.py
COPY devel/ci/integration/resultsdb/httpd.conf /etc/httpd/conf.d/resultsdb.conf
COPY devel/ci/integration/resultsdb/fedora-messaging.toml /etc/fedora-messaging/config.toml

EXPOSE 80
CMD ["/usr/sbin/httpd", "-DFOREGROUND"]
