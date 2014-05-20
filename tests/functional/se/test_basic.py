import time

from selenium import webdriver
from tests.functional import SeleniumTestController

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By

class BasicTest(SeleniumTestController):
    """
    Test the basic framework for the webapp (login, logout, naviagation, etc.)
    """
    
    def setUp(self):
        super(BasicTest, self).setUp()
        self.login()
    
    def tearDown(self):
        self.logout()
        super(BasicTest, self).tearDown()
        
    def test_auth_failed(self):
        """ Test login failure. """
        self.logout()
        
        self.wd.find_element_by_id("username").send_keys("op1")
        self.wd.find_element_by_id("password").send_keys("xxxx")
        self.wd.find_element_by_css_selector("button.submit").click() # implicit wait

        self.assertIn('Log In', self.wd.title)
        
        self.assertTrue(self.is_element_present(By.CLASS_NAME, "form_error"))
        
        errors = self.wd.find_elements(By.CLASS_NAME, "form_error")
        print errors
        self.assertEquals(1, len(errors))
        self.assertEquals("Invalid username/password.", errors[0].text)
    
    def test_main_navigation(self):
        """ Test the functionality of the main navigation bar. """
        self.wd.find_element(By.ID, "nav-groups").click()
        self.assertEquals('Group List', self.wd.title)
        
        self.wd.find_element(By.ID, "nav-resources").click()
        self.assertEquals('Add Resource', self.wd.title)
        
        self.wd.find_element(By.ID, "nav-users").click()
        self.assertEquals('Operator List', self.wd.title)
        
        self.wd.find_element(By.ID, "nav-access").click()
        self.assertEquals('Access Level List', self.wd.title)
        
        self.wd.find_element(By.ID, "nav-auditlog").click()
        self.assertEquals('Audit Log', self.wd.title)
        
        self.wd.find_element(By.ID, "nav-logout").click()
        self.assertIn('Log In', self.wd.title)