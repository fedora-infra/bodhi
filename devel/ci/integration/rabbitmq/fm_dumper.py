import json

DESTINATION = "/var/log/fedora-messaging/messages.log"


def callback(message):
    print(message)
    serialized = json.dumps(message._dump())
    with open(DESTINATION, "a") as f:
        f.write(serialized)
        f.write("\n")
