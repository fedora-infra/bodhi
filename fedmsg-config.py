import random

import socket
hostname = socket.gethostname()

config = dict(
    endpoints={
        "relay_outbound": ["tcp://*:4001"],
        "bodhi.%s" % hostname: [
            # Here we use a random port number just so the test suite can run in
            # parallel
            "tcp://*:%i" % random.randint(4000, 9000)
        ],
    },

    relay_inbound="tcp://127.0.0.1:2003",
    environment="dev",
    high_water_mark=0,
    io_threads=1,
    irc=[],
    zmq_enabled=True,
    zmq_strict=False,
)
