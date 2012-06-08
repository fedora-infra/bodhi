config = dict(
    # Set this to dev if you're hacking on fedmsg or an app.
    # Set to stg or prod if running in the Fedora Infrastructure
    environment="dev",

    # Default is 0
    high_water_mark=0,
    io_threads=1,

    ## For the fedmsg-hub and fedmsg-relay. ##

    # We almost always want the fedmsg-hub to be sending messages with zmq as
    # opposed to amqp or stomp.
    zmq_enabled=True,

    # When subscribing to messages, we want to allow splats ('*') so we tell the
    # hub to not be strict when comparing messages topics to subscription
    # topics.
    zmq_strict=False,
)
