config = dict(
    # Options for the fedmsg-irc service.
    irc=[
        dict(
            network='irc.freenode.net',
            port=6667,
            nickname='fedmsg-bot',
            channel='test-fedmsg',
            make_pretty=True,
            filters=dict(
                topic=[],
                body=['lub-dub'],
            )
        ),
        dict(
            network='irc.freenode.net',
            port=6667,
            nickname='fedmsg-bot',
            channel='test-fedmsg2',
            make_pretty=True,
            filters=dict(
                topic=[],
                body=['lub-dub'],
            ),
        ),
    ],
)
