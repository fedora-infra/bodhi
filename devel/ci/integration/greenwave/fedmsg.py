config = dict(
    sign_messages=False,
    active=True,
    greenwave_cache={},
    environment='testing',
    relay_inbound=["tcp://fedmsg:9941"],
    greenwave_api_url='https://greenwave/api/v1.0',
    endpoints=dict(
        prod_gateway=[
            'tcp://stg.fedoraproject.org:9940',
        ],
    ),
)
