# These are general bodhi fedmsg settings, mostly for app dev.

import socket
hostname = socket.gethostname().split('.')[0]

config = dict(
    endpoints={
        "bodhi.%s" % hostname: [
            'tcp://127.0.0.1:8084',
            'tcp://127.0.0.1:8085',
            'tcp://127.0.0.1:8086',
            'tcp://127.0.0.1:8087',
        ]
    }
)
