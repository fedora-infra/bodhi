FROM quay.io/factory2/greenwave:prod
LABEL \
  name="greenwave" \
  vendor="Fedora Infrastructure" \
  maintainer="Aurelien Bompard <abompard@fedoraproject.org>" \
  license="MIT"

# fedmsg needs a username.
ENV USER=greenwave

# Become root during build to chmod
USER 0

# Make sure fedmsg can write its CRL.
RUN chmod 777 /var/run/fedmsg/

RUN mkdir -p /etc/greenwave
COPY devel/ci/integration/greenwave/fedmsg.py /etc/fedmsg.d/zz_greenwave.py
COPY devel/ci/integration/greenwave/settings.py /etc/greenwave/settings.py
COPY devel/ci/integration/greenwave/policy.yaml /etc/greenwave/fedora.yaml

# Become non-root again
USER 1001

ENTRYPOINT ["/bin/sh", "-c", "gunicorn-3 --workers 8 --bind 0.0.0.0:8080 --access-logfile=- --error-logfile=- --enable-stdio-inheritance greenwave.wsgi:app"]
