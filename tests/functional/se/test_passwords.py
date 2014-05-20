import time

from selenium import webdriver

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.common.by import By

from ensconce.dao import resources, groups

from tests.functional import SeleniumTestController

class PasswordsTest(SeleniumTestController):
    """
    
    """
    
    def setUp(self):
        super(PasswordsTest, self).setUp()
        self.login()
        
    
    def tearDown(self):
        self.logout()
        super(PasswordsTest, self).tearDown()
    
    
    def test_view_pw(self):
        """ Test viewing password contents; ensure matches db. """
        rsc = resources.get_by_name("host1.example.com")
        self.open_url('/resource/view/{0}'.format(rsc.id))
        
        user0 = rsc.passwords.filter_by(username='user0').one()
        
        el = self.wd.find_element(By.ID, "pw{0}".format(user0.id))
        self.assertFalse(el.is_displayed())
        
        link = self.wd.find_element(By.ID, "lnk{0}".format(user0.id))
        
            
        link.click()
        
        def is_displayed(el):
            if el.is_displayed():
                return el
        
        found_el = WebDriverWait(self.wd, 10).until(lambda d: is_displayed(d.find_element(By.ID, "pw{0}".format(user0.id))))
        
        self.assertEqual(user0.password_decrypted, el.get_attribute("value"))
        
    
    def test_add_gen(self):
        """ Test adding a new password and generating pw """
        rsc = resources.get_by_name("host1.example.com")
        self.open_url('/resource/view/{0}'.format(rsc.id))
        self.submit_form("add_password_form")
        
        self.assertEqual("Add a Password", self.wd.title)
        
        el = self.wd.find_element(By.ID, "username")
        el.send_keys('user5')
        
        # Generate a password
        self.wd.find_element(By.ID, "generate-pw-button").click()
        
        def has_value(element):
            if element.get_attribute("value") != "":
                return element
            
        genpw_el = WebDriverWait(self.wd, 10).until(lambda d: has_value(d.find_element(By.ID, "mypassword")))
        generated_password = genpw_el.get_attribute('value')
        
        # Copy it in
        self.wd.find_element(By.ID, "copy-pw-button").click()
            
        self.assertEquals(generated_password, self.wd.find_element(By.ID, "password_decrypted").get_attribute('value'))
        
        self.submit_form("password_form")
        
        self.assertEqual("View Resource", self.wd.title)
        
        user5 = rsc.passwords.filter_by(username='user5').one()
        
        self.assert_notification("Password created: user5 (id={0})".format(user5.id))
        self.assert_in_list_table("user5", table=2, is_link=False)
        
        self.assertEqual(generated_password, user5.password_decrypted)
        
        
    def test_add_duplicate(self):
        """ Test adding a duplicate password. """

        rsc = resources.get_by_name("host1.example.com")
        self.open_url('/resource/view/{0}'.format(rsc.id))
        self.submit_form("add_password_form")
        
        self.assertEqual("Add a Password", self.wd.title)
        
        el = self.wd.find_element(By.ID, "username")
        el.send_keys('user4')
        
        el = self.wd.find_element(By.ID, "password_decrypted")
        el.send_keys('1234')
        
        self.submit_form("password_form")
        
        self.assertEqual("View Resource", self.wd.title)
        count = rsc.passwords.filter_by(username='user4').count()
        self.assertEquals(2, count)