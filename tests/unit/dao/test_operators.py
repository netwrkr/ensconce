import random

from ensconce.dao import operators
from ensconce import exc

from tests import BaseModelTest

class TestOperatorsDao(BaseModelTest):

    def test_get(self):
        random_group = random.choice(self.data.operators.values())
        match = operators.get(random_group.id)
        self.assertIs(random_group, match)
        
        with self.assertRaises(TypeError):
            operators.get(None)
        
        
        with self.assertRaisesRegexp(exc.NoSuchEntity, r'Operator'):
            operators.get(0)
            
        no_match = operators.get(0, assert_exists=False)
        self.assertIs(None, no_match)
        
        
    def test_list(self):
        
        gs = operators.list()
        
        # Postgres is sorting case-insensitive here.  This 
        # probably is db-specific, so we may need a better assertion.
        
        gnames = [g.username for g in gs]
        print gnames
        print sorted(gnames, key=unicode.lower)
        self.assertEquals(sorted(gnames, key=unicode.lower), gnames)
        
        