import random

from ensconce.dao import groups
from ensconce import exc, search

from tests import BaseModelTest

class TestSearch(BaseModelTest):
    
    def test_tagsearch_basic(self):
        results = search.tagsearch(['tagone'])
        self.assertEquals(3, len(results.resource_matches))
        self.assertEquals(2, len(results.password_matches))
    
    def test_tagsearch_multi(self):
        results = search.tagsearch(['tagone', 'tagtwo'])
        self.assertEquals(2, len(results.resource_matches))
        self.assertEquals(2, len(results.password_matches))
        
    def test_tagsearch_partial(self):
        results = search.tagsearch(['tagone', 'tagtwo'], search_resources=False)
        self.assertEquals(0, len(results.resource_matches))
        self.assertEquals(2, len(results.password_matches))
        
        results = search.tagsearch(['tagone', 'tagtwo'], search_passwords=False)
        self.assertEquals(2, len(results.resource_matches))
        self.assertEquals(0, len(results.password_matches))
        
    def test_tagsearch_prefix_naive(self):
        results = search.tagsearch(['tagprefix'])
        self.assertEquals(1, len(results.resource_matches))
        self.assertEquals(2, len(results.password_matches))
        
    def test_tagsearch_prefixsuffix(self):
        results = search.tagsearch(['tagprefix:'])
        self.assertEquals(1, len(results.resource_matches))
        self.assertEquals(1, len(results.password_matches))
        
        results = search.tagsearch([':tagone'])
        self.assertEquals(1, len(results.resource_matches))
        self.assertEquals(2, len(results.password_matches))