import socket
hostname = socket.gethostname()

config = dict(
    # This is a dict of possible addresses from which fedmsg can send
    # messages.  fedmsg.init(...) requires that a 'name' argument be passed
    # to it which corresponds with one of the keys in this dict.
    endpoints={
        # This is the output side of the relay to which all other
        # services can listen.
        "relay_outbound": ["tcp://*:4001"],

        # For other, more 'normal' services, fedmsg will try to guess the
        # name of it's calling module to determine which endpoint definition
        # to use.  This can be overridden by explicitly providing the name in
        # the initial call to fedmsg.init(...).
        "bodhi.%s" % hostname: ["tcp://*:3001"],
        "fas.%s" % hostname: ["tcp://*:3002"],
        "fedoratagger.%s" % hostname: ["tcp://*:3003"],
        "mediawiki.%s" % hostname: ["tcp://*:3004"],
        "pkgdb.%s" % hostname: ["tcp://*:3005"],

        "busmon.%s" % hostname: ["tcp://*:3006"],
    },

    # This is the address of an active->passive relay.  It is used for the
    # fedmsg-logger command which requires another service with a stable
    # listening address for it to send messages to.
    # It is also used by the git-hook, for the same reason.
    # It is also used by the mediawiki php plugin which, due to the oddities of
    # php, can't maintain a single passive-bind endpoint of it's own.
    relay_inbound="tcp://127.0.0.1:2003",
)
