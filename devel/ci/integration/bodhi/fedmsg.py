config = {
    'sign_messages': False,
    'active': True,
    # TODO: setup a container for the fedmsg relay
    'relay_inbound': ['tcp://fedmsg:9941'],
    # 'bodhi': ['tcp://busgateway.fedoraproject.org:9941'],
    'environment': 'testing',
    'endpoints': {
        'prod_gateway': ['tcp://fedoraproject.org:9940']
    }
}
