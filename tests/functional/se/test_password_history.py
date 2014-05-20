import time
import re

from selenium import webdriver
from tests.functional import SeleniumTestController

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By

from ensconce.model import meta
from ensconce.dao import passwords

class PasswordHistoryTest(SeleniumTestController):
    """
    Test the basic framework for the webapp (login, logout, naviagation, etc.)
    """
    
    def setUp(self):
        super(PasswordHistoryTest, self).setUp()
        self.login()
        
    
    def tearDown(self):
        self.logout()
        super(PasswordHistoryTest, self).tearDown()

    def assert_in_group_list(self, name):
        firstcols = self.wd.find_elements(By.XPATH, "//table/tbody/tr/td[1]/a")
        group_names = [c.text for c in firstcols]
        self.assertIn(name, group_names)

    def navigate_to_resource(self, name):
        self.open_url('/resource/list')
        time.sleep(0.3)
        self.wd.find_element(By.LINK_TEXT, name).click()
        time.sleep(0.3)
        
    def test_basic(self):
        """ Test basic password history feature. """
        self.navigate_to_resource("host1.example.com")
        
        history_links = self.wd.find_elements(By.LINK_TEXT, "History")
        history_links[0].click()
        time.sleep(0.5) # FIXME: replace with waiting selector
        
        els = self.wd.find_elements(By.XPATH, ".//*[@id='content']/table[2]/tbody/tr/td")
        self.assertEqual(1, len(els), "Expected table with 1 [no-content-message] row.")
        self.assertTrue(els[0].text.startswith("No password"))
        
        self.wd.find_element(By.ID, "edit-password-btn").click()
        # Now we're editing the password
        self.wd.find_element(By.ID, "password_decrypted").send_keys("qwerty")
        self.wd.find_element(By.ID, "save-password-btn").click()
        
        # Now go back to the passwords list
        self.navigate_to_resource("host1.example.com")
        history_links = self.wd.find_elements(By.LINK_TEXT, "History")
        history_links[0].click()
        
        time.sleep(0.5) # FIXME: replace with waiting selector
        
        input_el = self.wd.find_element(By.XPATH, "//*[@id='content']/table[2]/tbody/tr[1]/td[1]/form/input")
        self.assertTrue(input_el is not None, "Expected to find an input element for pw hist.")
        
    def test_delete(self):
        """ Test deleting a password with history. """
        self.navigate_to_resource("host1.example.com")
        
        history_links = self.wd.find_elements(By.LINK_TEXT, "History")
        history_links[0].click()
        
        time.sleep(0.5) # FIXME: replace with waiting selector
        
        els = self.wd.find_elements(By.XPATH, ".//*[@id='content']/table[2]/tbody/tr/td")
        self.assertEqual(1, len(els), "Expected table with 1 [no-content-message] row.")
        self.assertTrue(els[0].text.startswith("No password"))
        
        self.wd.find_element(By.ID, "edit-password-btn").click()
        # Now we're editing the password
        self.wd.find_element(By.ID, "password_decrypted").send_keys("qwerty")
        self.wd.find_element(By.ID, "save-password-btn").click()
        
        # Now go back to the passwords list
        self.navigate_to_resource("host1.example.com")
        history_links = self.wd.find_elements(By.LINK_TEXT, "History")
        history_links[0].click()
        
        time.sleep(0.5) # FIXME: replace with waiting selector
        
        input_el = self.wd.find_element(By.XPATH, "//*[@id='content']/table[2]/tbody/tr[1]/td[1]/form/input")
        self.assertTrue(input_el is not None, "Expected to find an input element for pw hist.")
        
        self.navigate_to_resource("host1.example.com")
        delete_links = self.wd.find_elements(By.LINK_TEXT, "Delete")
        delete_links[0].click()
        
        alert = self.wd.switch_to_alert()
        
        m = re.search(r'\(id=(\d+)\)', alert.text)
        pw_id = m.group(1)
        
        self.assertRegexpMatches(alert.text, r'^Are you sure you want to remove password for user0 \(id=\d+\)$')
        alert.accept()
        
                
        self.assert_notification("Password deleted: user0 (id={0})".format(pw_id))
        self.assert_not_in_list_table("user1")
        
        
    def test_multiple(self):
        """ Test setting multiple passwords. """
        self.navigate_to_resource("host1.example.com")
        
        history_links = self.wd.find_elements(By.LINK_TEXT, "History")
        history_links[0].click()
        
        time.sleep(0.5) # The click isn't auto-waiting ...
        
        els = self.wd.find_elements(By.XPATH, ".//*[@id='content']/table[2]/tbody/tr/td")
        self.assertEqual(1, len(els), "Expected table with 1 [no-content-message] row.")
        self.assertTrue(els[0].text.startswith("No password history"))
        
        pw_id = self.wd.current_url.split('/')[-1]
        
        session = meta.Session()
        
        passwords.modify(pw_id, password="First Change")
        session.commit()
        
        time.sleep(1)
        
        passwords.modify(pw_id, password="Second Change")
        session.commit()
        
        self.wd.refresh()
        
        curr_pw = self.wd.find_element(By.ID, "current-password")
        self.assertEqual("Second Change", curr_pw.get_attribute("value"))
        
        els = self.wd.find_elements(By.XPATH, ".//*[@id='content']/table[2]/tbody/tr")
        self.assertEqual(2, len(els), "Expected table with 2 rows.")
        
        input_el = self.wd.find_element(By.XPATH, "//*[@id='content']/table[2]/tbody/tr[1]/td[1]/form/input")
        self.assertTrue(input_el is not None, "Expected to find an input element for pw hist.")
        self.assertEqual("First Change", input_el.get_attribute("value"))
    
        
        
        
