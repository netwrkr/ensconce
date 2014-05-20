import requests

from ensconce.config import config

from tests.functional import FunctionalTestController

class BaseServerTest(FunctionalTestController):
    
    def setUp(self):
        super(BaseServerTest, self).setUp()

    def tearDown(self):
        super(BaseServerTest, self).tearDown()
        #self.server_thread.
    
    def url(self, *args, **kwargs):
        base = 'http://{0}:{1}/'.format('localhost', config['server.socket_port'])
        return base + '/'.join(args)
    
    def test_login(self):
        """ Test login. """
        url = self.url('process_login')
        r = requests.post(url, data={"username": "op1", "password": "pw1"})
        print r.text
        self.assertIn('Welcome, op1', r.text)