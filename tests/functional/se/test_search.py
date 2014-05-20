import time

from selenium import webdriver

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.common.by import By

from ensconce.dao import resources, groups

from tests.functional import SeleniumTestController

class SearchTest(SeleniumTestController):
    """
    Test resources module.
    """
    
    def setUp(self):
        super(SearchTest, self).setUp()
        self.login()
        
    
    def tearDown(self):
        self.logout()
        super(SearchTest, self).tearDown()

     
    def test_search_single(self):
        """ Test search when there is a single match. """
        el = self.wd.find_element(By.ID, "searchstr")
        el.send_keys("BoA")
        self.submit_form("search_form")
        self.assertEquals('View Resource', self.wd.title)
        self.assert_in_data_table('BoA', row=1)