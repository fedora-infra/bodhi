set -m

# Start RabbitMQ
su rabbitmq -s /bin/sh -c "cd /var/lib/rabbitmq ; /usr/lib/rabbitmq/bin/rabbitmq-server" &
for i in `seq 60`; do
    echo "Waiting for RabbitMQ to start up ($i)"
    rabbitmqctl status &>/dev/null && break
    sleep 1
done

# Start the Fedora Messaging dumper
export PYTHONPATH=/etc/fedora-messaging
fedora-messaging consume
