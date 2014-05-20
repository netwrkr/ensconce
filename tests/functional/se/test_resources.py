import time

from selenium import webdriver

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.common.by import By

from ensconce.dao import resources, groups

from tests.functional import SeleniumTestController

class ResourcesTest(SeleniumTestController):
    """
    Test resources module.
    """
    
    def setUp(self):
        super(ResourcesTest, self).setUp()
        self.login()
        
    
    def tearDown(self):
        self.logout()
        super(ResourcesTest, self).tearDown()


    def test_sub_navigation(self):
        """ Test the resource sub nav. """
        
        self.open_url('/resource/list')
        self.wd.find_element(By.ID, "subnav-list").click()
        time.sleep(0.5) # FIXME: Need to figure out how to wait on page loads; this is supposed to happen automatically ...
        self.assertEquals('Resource List', self.wd.title)
        
        self.open_url('/resource/list')
        self.wd.find_element(By.ID, "subnav-create").click()
        time.sleep(0.5) # FIXME: Need to figure out how to wait on page loads; this is supposed to happen automatically ...
        self.assertEquals('Add Resource', self.wd.title)
        
        # Copy/paste to check the other page
        self.open_url('/resource/add')
        self.wd.find_element(By.ID, "subnav-list").click()
        time.sleep(0.5) # FIXME: Need to figure out how to wait on page loads; this is supposed to happen automatically ...
        self.assertEquals('Resource List', self.wd.title)
        
        self.open_url('/resource/add')
        self.wd.find_element(By.ID, "subnav-create").click()
        time.sleep(0.5) # FIXME: Need to figure out how to wait on page loads; this is supposed to happen automatically ...
        self.assertEquals('Add Resource', self.wd.title)
    
    def test_add_no_group(self):
        """ Test adding a resource w/o specifying a group. """
        self.open_url('/resource/add')
        name = "ResourceTest.test_add_fail"
        el = self.wd.find_element(By.ID, "name")
        el.send_keys(name)
        self.submit_form("resource_form")
        self.assertEquals('Add Resource', self.wd.title)
        
    def test_add_success(self):
        """ Test adding a resource. """
        self.open_url('/resource/add')
        name = "ResourceTest.test_add_success"
        el = self.wd.find_element(By.ID, "name")
        el.send_keys(name)
        
        # Choose '6th group' from the select list.
        sel = Select(self.wd.find_element(By.ID, "group_ids"))
        sel.select_by_visible_text("6th group")
        
        self.submit_form("resource_form")
        self.assertEquals('View Resource', self.wd.title)
        self.assert_in_data_table(name, row=1)
        
        self.open_url('/resource/list')
        self.assertEquals('Resource List', self.wd.title)
        
        self.assert_in_list_table(name, nobr=True)
    
    def test_add_duplicate(self):
        """ Test adding a resource with duplicate name. """
        self.open_url('/resource/add')
        
        name = "Bikeshed PIN"
        el = self.wd.find_element(By.ID, "name")
        el.send_keys(name)
        
        # Choose '6th group' from the select list.
        sel = Select(self.wd.find_element(By.ID, "group_ids"))
        sel.select_by_visible_text("First Group")
        
        self.submit_form("resource_form")
        self.assert_form_error("Resource \"{0}\" already exists in group \"First Group\".".format(name))
        

    def test_edit_duplicate(self):
        """ Test editing a resource and specifying duplicate name. """
        
        name = "Bikeshed PIN"
        new_name = "BoA"  # A name we know to exist in First Group
        r1 = resources.get_by_name(name)
        
        self.open_url('/resource/edit/{0}'.format(r1.id))
        
        el = self.wd.find_element(By.ID, "name")
        el.clear()
        el.send_keys(new_name)
        
        self.submit_form("resource_form")
        self.assert_form_error("Resource \"{0}\" already exists in group \"First Group\".".format(new_name))
        
    def test_edit_link(self):
        """ Test clicking the edit link (prompt) """
        r = resources.get_by_name("BoA")
        
        self.open_url('/resource/list')
        
        editlink = self.wd.find_element(By.ID, "edit-link-{0}".format(r.id))
        editlink.click()
        time.sleep(0.5) # FIXME: Need to figure out how to wait on page loads; this is supposed to happen automatically ...
        
        self.assertEquals('Edit Resource', self.wd.title)
        
        namefield = self.wd.find_element(By.ID, "name")
        self.assertEquals("BoA", namefield.get_attribute('value'))

    def test_delete_link_no_passwords(self):
        """ Test clicking the delete link when no passwords. (prompt) """
        r = resources.get_by_name("Bikeshed PIN")
        
        self.open_url('/resource/list')
        
        deletelink = self.wd.find_element(By.ID, "delete-link-{0}".format(r.id))
        deletelink.click()
        
        alert = self.wd.switch_to_alert()
        self.assertEqual("Are you sure you want to remove resource {0} (id={1})".format(r.name, r.id), alert.text)
        alert.accept()
        
        self.assert_notification("Resource deleted: {0} (id={1})".format(r.name, r.id))
        self.assert_not_in_list_table(r.name)
        
    def test_delete_link_passwords(self):
        """ Test clicking the delete link with passwords (confirm page) """
        r = resources.get_by_name("BoA")
        
        self.open_url('/resource/list')
        
        deletelink = self.wd.find_element(By.ID, "delete-link-{0}".format(r.id))
        deletelink.click()
        
        self.assertEquals('Delete Resource', self.wd.title)
        
        self.submit_form("delete_form")
        
        alert = self.wd.switch_to_alert()
        self.assertEqual("Are you sure you wish to permanently delete this resource and passwords?", alert.text)
        alert.accept()
        
        self.assert_notification("Resource deleted: {0} (id={1})".format(r.name, r.id))
        self.assert_not_in_list_table(r.name)