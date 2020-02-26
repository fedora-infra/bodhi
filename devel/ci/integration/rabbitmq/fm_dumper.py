from fedora_messaging.message import dumps

DESTINATION = "/var/log/fedora-messaging/messages.log"


def callback(message):
    print(message)
    serialized = dumps(message)
    with open(DESTINATION, "a") as f:
        f.write(serialized)
        f.write("\n")
