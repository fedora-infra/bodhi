FROM fedora:29
LABEL \
  name="rabbitmq" \
  vendor="Fedora Infrastructure" \
  maintainer="Aurelien Bompard <abompard@fedoraproject.org>" \
  license="MIT"

# Install deps
RUN yum install -y \
    rabbitmq-server \
    fedora-messaging \
    hostname \
    /bin/ps

RUN rabbitmq-plugins --offline enable rabbitmq_management && rm -f /root/.erlang.cookie

COPY devel/ci/integration/rabbitmq/start.sh /etc/rabbitmq/start.sh
COPY devel/ci/integration/rabbitmq/fedora-messaging.toml /etc/fedora-messaging/config.toml
COPY devel/ci/integration/rabbitmq/fm_dumper.py /etc/fedora-messaging/fm_dumper.py
RUN mkdir -p /var/log/fedora-messaging/

EXPOSE 4369 5671 5672 25672
CMD ["bash", "/etc/rabbitmq/start.sh"]
