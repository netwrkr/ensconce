import time

from selenium import webdriver

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By

from ensconce.dao import operators

from tests.functional import SeleniumTestController

class OperatorsTest(SeleniumTestController):
    """
    Test the basic framework for the webapp (login, logout, naviagation, etc.)
    """
    
    def setUp(self):
        super(OperatorsTest, self).setUp()
        self.login()
        
    
    def tearDown(self):
        self.logout()
        super(OperatorsTest, self).tearDown()
        
    def assert_in_operator_list(self, name):
        firstcols = self.wd.find_elements(By.XPATH, "//table/tbody/tr/td[1]/a")
        names = [c.text for c in firstcols]
        self.assertIn(name, names)
    
    def assert_not_in_operator_list(self, name):
        firstcols = self.wd.find_elements(By.XPATH, "//table/tbody/tr/td[1]/a")
        names = [c.text for c in firstcols]
        self.assertNotIn(name, names)
        
    def test_sub_navigation(self):
        """ Test the operators sub nav. """
        self.open_url('/user/list')
        self.wd.find_element(By.ID, "subnav-list").click()
        time.sleep(0.5) # FIXME: Need to figure out how to wait on page loads; this is supposed to happen automatically ...
        self.assertEquals('Operator List', self.wd.title)
        
        self.open_url('/user/list')
        self.wd.find_element(By.ID, "subnav-create").click()
        time.sleep(0.5) # FIXME: Need to figure out how to wait on page loads; this is supposed to happen automatically ...
        self.assertEquals('Add Operator', self.wd.title)
        
        # Copy/paste to check the other page
        self.open_url('/user/add')
        self.wd.find_element(By.ID, "subnav-list").click()
        time.sleep(0.5) # FIXME: Need to figure out how to wait on page loads; this is supposed to happen automatically ...
        self.assertEquals('Operator List', self.wd.title)
        
        self.open_url('/user/add')
        self.wd.find_element(By.ID, "subnav-create").click()
        time.sleep(0.5) # FIXME: Need to figure out how to wait on page loads; this is supposed to happen automatically ...
        self.assertEquals('Add Operator', self.wd.title)
    
    def test_add_success_no_pw(self):
        """ Test adding an operator w/o password. """
        self.open_url('/user/add')
        name = "operator.test_add_success"
        el = self.wd.find_element(By.ID, "username")
        el.send_keys(name)
        
        self.submit_form("operator_form")
        self.assertEquals('Operator List', self.wd.title)
        self.assert_in_list_table(name)
    
    def test_add_success_pw(self):
        """ Test adding an operator w/ password. """
        self.open_url('/user/add')
        name = "operator.test_add_success"
        password = "XPassWord!"
        
        el = self.wd.find_element(By.ID, "username")
        el.send_keys(name)
        
        el = self.wd.find_element(By.ID, "password")
        el.send_keys(password)
        
        self.submit_form("operator_form")
        self.assertEquals('Operator List', self.wd.title)
        self.assert_in_operator_list(name)
        
        self.logout()
        self.login(name, password)
        
    def test_add_duplicate(self):
        """ Test adding an operator with duplicate name. """
        self.open_url('/user/add')
        
        el = self.wd.find_element(By.ID, "username")
        el.send_keys("op1")
        
        self.submit_form("operator_form")
        
        self.assert_form_error("Operator \"op1\" already exists.")
        
    def test_add_too_long(self):
        """ Test adding operator with too-long field values. """
        self.open_url('/user/add')
        el = self.wd.find_element(By.ID, "username")
        el.send_keys("X" * 256)
        self.submit_form("operator_form")
        self.assert_form_error("Field cannot be longer than 255 characters.")

    def test_add_empty(self):
        """ Test adding a user with empty username. """
        self.open_url('/user/add')
        el = self.wd.find_element(By.ID, "username")
        el.send_keys("")
        self.submit_form("operator_form")
        # Since we're using HTML5 'required' we'll just assert that form did not submit.
        self.assertEquals('Add Operator', self.wd.title)
        
    def test_edit_username(self):
        """
        Test changing username.
        """
        # We want to edit the username for an arbitrary not-externally-managed user.
        operator = operators.get_by_username("op1")
    
        old_username = operator.username
        new_username = operator.username + "-new"
        
        self.open_url('/user/edit/{0}'.format(operator.id))
        el = self.wd.find_element(By.ID, "username")
        el.clear()
        el.send_keys(new_username)
        self.submit_form("operator_form")
    
        self.assertEqual("Operator List", self.wd.title)
        self.assert_in_list_table(new_username)
        self.assert_not_in_list_table(old_username)
        
        self.logout()
        self.login(new_username, "pw1") # pw from test data; we did not change it.
    
    def test_edit_password(self):
        """
        Test changing password.
        """
        # We want to edit the username for an arbitrary not-externally-managed user.
        operator = operators.get_by_username("op1")
    
        new_password = "__pw1__"
        self.open_url('/user/edit/{0}'.format(operator.id))
        el = self.wd.find_element(By.ID, "password")
        el.clear()
        el.send_keys(new_password)
        self.submit_form("operator_form")
    
        self.assertEqual("Operator List", self.wd.title)
        self.assert_in_list_table("op1")
        
        self.logout()
        self.login("op1", new_password) # pw from test data; we did not change it.
        self.logout()
        self.fail_login("op1", "pw1")
        