FROM quay.io/fedora/fedora:latest
LABEL \
  name="redis" \
  vendor="Fedora Infrastructure" \
  maintainer="Mattia Verga <mattia@fedoraproject.org>" \
  license="MIT"

# Install deps
RUN yum install -y \
    valkey

RUN echo "requirepass This_Is_JustAT3st" >> /etc/valkey/valkey-docker.conf

EXPOSE 6379

CMD ["valkey-server", "--bind", "0.0.0.0", "--protected-mode", "no", "--loglevel", "debug"]
