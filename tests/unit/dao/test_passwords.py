import random

from ensconce.dao import passwords
from ensconce import exc

from tests import BaseModelTest

class TestPasswordsDao(BaseModelTest):

    def test_get(self):
        with self.assertRaisesRegexp(exc.NoSuchEntity, r'Password'):
            passwords.get(0)
            
        no_match = passwords.get(0, assert_exists=False)
        self.assertIs(None, no_match)
        