from fedora.client import OpenIdBaseClient

BASE_URL = 'http://127.0.0.1:6543'


class BodhiClient(OpenIdBaseClient):

    def __init__(self, base_url=BASE_URL, **kwargs):
        super(BodhiClient, self).__init__(base_url, **kwargs)

    def new(self, **kwargs):
        return self.send_request('/updates/', verb='POST', auth=True,
                                 data=kwargs)

    def query(self, **kwargs):
        return self.send_request('/updates/', verb='GET', params=kwargs)
