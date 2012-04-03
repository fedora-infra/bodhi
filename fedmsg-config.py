# This file's extension says .ini indicating it is a config file, but it's
# really a python source file containing the configuration for fedmsg.

config = dict(
    # This is a dict of possible addresses from which fedmsg can send
    # messages.  fedmsg.init(...) requires that a 'name' argument be passed
    # to it which corresponds with one of the keys in this dict.
    endpoints=dict(

        # A default bind endpoint.  Just here for debugging.  All
        # services should be named.
        default="tcp://*:6543",

        # This is the output side of the relay to which all other
        # services can listen.
        relay_outbound="tcp://*:4001",

        # For other, more 'normal' services, fedmsg will try to guess the
        # name of it's calling module to determine which endpoint definition
        # to use.  This can be overridden by explicitly providing the name in
        # the initial call to fedmsg.init(...).
        bodhi="tcp://*:3001",
        fas="tcp://*:3002",
        fedoratagger="tcp://*:3003",
    ),

    # This is the address of an active->passive relay.  It is used for the
    # fedmsg-logger command which requires another service with a stable
    # listening address for it to send messages to.
    relay_inbound="tcp://127.0.0.1:2003",


    # Set this to dev if you're hacking on fedmsg or an app.
    # Set to stg or prod if running in the Fedora Infrastructure
    environment="dev",

    # Default is 0
    high_water_mark=1,

    io_threads=1,
)
