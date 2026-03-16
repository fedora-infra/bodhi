FROM quay.io/redhat-user-workloads/exd-sp-rhel-wf-tenant/resultsdb:prod-fedora
LABEL \
  name="resultsdb" \
  vendor="Fedora Infrastructure" \
  maintainer="Mattia Verga <mattia@fedoraproject.org>" \
  license="MIT"

# Configuration
COPY devel/ci/integration/resultsdb/settings.py /etc/resultsdb/settings.py
COPY devel/ci/integration/resultsdb/fedora-messaging.toml /etc/fedora-messaging/config.toml

