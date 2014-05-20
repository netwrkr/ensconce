import os.path
import hashlib
import unittest2
import binascii

from ensconce.model import meta
from ensconce.crypto import CombinedMasterKey, state, util as crypto_util
from ensconce.config import init_config, init_model, init_logging, config

from tests.data import populate

TEST_INI = os.path.join(os.path.dirname(__file__), 'test.ini')
LOGGING_INI = os.path.join(os.path.dirname(__file__), 'logging.cfg')

class BaseTest(unittest2.TestCase):
    
    @classmethod
    def setUpClass(cls):
        """
        Initialize the encryption engine with a test key.
        """
        init_config(configfiles=[TEST_INI])
        init_logging(configfiles=[LOGGING_INI])

class BaseModelTest(BaseTest):
    
    @classmethod
    def setUpClass(cls):
        """
        Initialize the database.
        
        We also read and store the encryption key here (but actual state setup
        happens in in setUp method).
        """
        super(BaseModelTest, cls).setUpClass()
        init_model(config)
        if not  config.get('debug.secret_key'):
            raise Exception("Tests only work with debug.secret_key set to a valid key.")

        cls.SECRET_KEY = CombinedMasterKey(binascii.unhexlify(open(config['debug.secret_key']).read().strip()))
            
    def setUp(self):    
        # We rely on the prsence of a local debug key for our tests.
        state.secret_key = self.SECRET_KEY
        self.data = populate.TestDataPopulator()
        self.data.depopulate()
        self.data.populate()
        
        
    def tearDown(self):
        super(BaseModelTest, self).tearDown()
        meta.Session().rollback() # This is very simple, but wont' work for the functional tests (not same thread)
        state.secret_key = None
        