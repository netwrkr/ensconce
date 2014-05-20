import random

from ensconce.dao import groups
from ensconce import exc

from tests import BaseModelTest

class TestGroupsDao(BaseModelTest):

    def test_get(self):
        random_group = random.choice(self.data.groups.values())
        match = groups.get(random_group.id)
        self.assertIs(random_group, match)
        
        with self.assertRaises(TypeError):
            groups.get(None)
        
        
        with self.assertRaisesRegexp(exc.NoSuchEntity, r'Group'):
            groups.get(0)
            
        no_match = groups.get(0, assert_exists=False)
        self.assertIs(None, no_match)
        
        
    def test_list(self):
        
        gs = groups.list()
        
        # Postgres is sorting case-insensitive here.  This 
        # probably is db-specific, so we may need a better assertion.
        
        gnames = [g.name for g in gs]
        print gnames
        print sorted(gnames, key=unicode.lower)
        self.assertEquals(sorted(gnames, key=unicode.lower), gnames)
        
        