import socket
hostname = socket.gethostname()

config = dict(
    endpoints={
        "relay_outbound": ["tcp://*:4001"],
        "bodhi.%s" % hostname: [
            # Here we list 10 endpoints so bodhi's test suite can run in
            # parallel.
            "tcp://*:3001",
            "tcp://*:3002",
            "tcp://*:3003",
            "tcp://*:3004",
            "tcp://*:3005",
            "tcp://*:3006",
            "tcp://*:3007",
            "tcp://*:3008",
            "tcp://*:3009",
            "tcp://*:3010",
        ],
    },

    relay_inbound="tcp://127.0.0.1:2003",
    environment="dev",
    high_water_mark=0,
    io_threads=1,
    irc=[],
    zmq_enabled=True,
    zmq_strict=False,

    sign_messages=False,
    validate_messages=False,
)
