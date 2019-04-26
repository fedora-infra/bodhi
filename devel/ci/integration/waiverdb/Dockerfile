FROM quay.io/factory2/waiverdb:prod
LABEL \
  name="waiverdb" \
  vendor="Fedora Infrastructure" \
  maintainer="Aurelien Bompard <abompard@fedoraproject.org>" \
  license="MIT"

# Become root during build to copy files
USER 0

RUN mkdir -p /etc/waiverdb
COPY devel/ci/integration/waiverdb/settings.py /etc/waiverdb/settings.py
COPY devel/ci/integration/waiverdb/fedora-messaging.toml /etc/fedora-messaging/config.toml

# Become non-root again
USER 1001
