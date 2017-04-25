# These are general bodhi fedmsg settings, mostly for app dev.

import socket
hostname = socket.gethostname().split('.')[0]

config = {
    'endpoints': {
        "bodhi.%s" % hostname: [
            'tcp://127.0.0.1:8084',
            'tcp://127.0.0.1:8085',
            'tcp://127.0.0.1:8086',
            'tcp://127.0.0.1:8087',
            'tcp://127.0.0.1:8088',
            'tcp://127.0.0.1:8089',
            'tcp://127.0.0.1:8090',
            'tcp://127.0.0.1:8091',
        ]
    },
    'sign_messages': False,
    'validate_signatures': False,
}
