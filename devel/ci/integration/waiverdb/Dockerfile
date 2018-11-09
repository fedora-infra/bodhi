FROM quay.io/factory2/waiverdb:prod
LABEL \
  name="waiverdb" \
  vendor="Fedora Infrastructure" \
  maintainer="Aurelien Bompard <abompard@fedoraproject.org>" \
  license="MIT"

# fedmsg needs a username.
ENV USER=waiverdb

# Become root during build to copy files
USER 0

# Make sure fedmsg can write its CRL.
RUN chmod 777 /var/run/fedmsg/

RUN mkdir -p /etc/waiverdb
COPY devel/ci/integration/waiverdb/fedmsg.py /etc/fedmsg.d/zz_waiverdb.py
COPY devel/ci/integration/waiverdb/settings.py /etc/waiverdb/settings.py

# Become non-root again
USER 1001
