import time

from selenium import webdriver


from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.common.by import By

from ensconce.dao import groups 

from tests.functional import SeleniumTestController

class GroupsTest(SeleniumTestController):
    """
    Test groups module.
    """
    
    def setUp(self):
        super(GroupsTest, self).setUp()
        self.login()
            
    def tearDown(self):
        self.logout()
        super(GroupsTest, self).tearDown()

    def test_sub_navigation(self):
        """ Test the groups sub nav. """
        self.open_url('/group/list')
        self.wd.find_element(By.ID, "subnav-list").click()
        time.sleep(0.5) # FIXME: Need to figure out how to wait on page loads; this is supposed to happen automatically ...
        self.assertEquals('Group List', self.wd.title)
        
        self.open_url('/group/list')
        self.wd.find_element(By.ID, "subnav-create").click()
        time.sleep(0.5) # FIXME: Need to figure out how to wait on page loads; this is supposed to happen automatically ...
        self.assertEquals('Add Group', self.wd.title)
        
        # Copy/paste to check the other page
        self.open_url('/group/add')
        self.wd.find_element(By.ID, "subnav-list").click()
        time.sleep(0.5) # FIXME: Need to figure out how to wait on page loads; this is supposed to happen automatically ...
        self.assertEquals('Group List', self.wd.title)
        
        self.open_url('/group/add')
        self.wd.find_element(By.ID, "subnav-create").click()
        time.sleep(0.5) # FIXME: Need to figure out how to wait on page loads; this is supposed to happen automatically ...
        self.assertEquals('Add Group', self.wd.title)
    
    def test_add_success(self):
        """ Test adding a group. """
        self.open_url('/group/add')
        name = "GroupsTest.test_add_success"
        el = self.wd.find_element(By.ID, "name")
        el.send_keys(name)
        self.submit_form("group_form")
        self.assertEquals('Group List', self.wd.title)
        self.assert_in_list_table(name)
         
    def test_add_duplicate(self):
        """ Test adding a group with duplicate name. """
        self.open_url('/group/add')
        el = self.wd.find_element(By.ID, "name")
        el.send_keys("First Group")
        self.submit_form("group_form")
        self.assert_form_error("Group \"First Group\" already exists.")
    
    def test_edit_rename(self):
        """ Test editing a group and giving a new name. """
        group = groups.get_by_name("First Group")
        new_name = 'BRAND-NEW-NAME'
        self.open_url('/group/edit/{0}'.format(group.id))
        el = self.wd.find_element(By.ID, "name")
        el.clear()
        el.send_keys(new_name)
        self.submit_form("group_form")
        self.assertEquals('Group List', self.wd.title)
        self.assert_in_list_table(new_name)
        
    def test_edit_duplicate(self):
        """ Test editing a group and specifying a duplicate name. """
        group = groups.get_by_name("First Group")
        new_name = '6th group'
        self.open_url('/group/edit/{0}'.format(group.id))
        el = self.wd.find_element(By.ID, "name")
        el.clear()
        el.send_keys(new_name)
        self.submit_form("group_form")
        self.assert_form_error("Group \"{0}\" already exists.".format(new_name))
        
    def test_add_too_long(self):
        """ Test adding a group with too-long name. """
        self.open_url('/group/add')
        el = self.wd.find_element(By.ID, "name")
        el.send_keys("X" * 256)
        self.submit_form("group_form")
        self.assert_form_error("Field cannot be longer than 255 characters.")
        
    def test_add_empty(self):
        """ Test adding a group with empty name. """
        self.open_url('/group/add')
        el = self.wd.find_element(By.ID, "name")
        el.send_keys("")
        self.submit_form("group_form")
        # Since we're using HTML5 'required' we'll just assert that form did not submit.
        self.assertEquals('Add Group', self.wd.title)
        

    def test_merge_validation(self):
        """ Test the validation on group merge feature. """
        self.open_url('/group/list')
        self.wd.find_element(By.ID, "subnav-merge").click()
        time.sleep(0.5) # FIXME: Need to figure out how to wait on page loads; this is supposed to happen automatically ...
        self.assertEquals('Merge Group', self.wd.title)
        
        sel = Select(self.wd.find_element(By.ID, "from_group_id"))
        sel.select_by_visible_text("6th group")
        
        sel = Select(self.wd.find_element(By.ID, "to_group_id"))
        sel.select_by_visible_text("6th group")
        
        self.submit_form("merge_form")
        self.assert_form_error("Cannot merge a group into itself.")
                
    def test_merge_nooverlap(self):
        """ Test the group merge feature (no overlap). """
        self.open_url('/group/list')
        
        # Sanity check
        el = self.wd.find_element(By.LINK_TEXT, "Second Group")
        el.click()
        time.sleep(0.5)
        
        self.assert_num_rows(1)
        
        self.open_url('/group/list')
        self.wd.find_element(By.ID, "subnav-merge").click()
        time.sleep(0.5) # FIXME: Need to figure out how to wait on page loads; this is supposed to happen automatically ...
        self.assertEquals('Merge Group', self.wd.title)
        
        sel = Select(self.wd.find_element(By.ID, "from_group_id"))
        sel.select_by_visible_text("6th group")
        
        sel = Select(self.wd.find_element(By.ID, "to_group_id"))
        sel.select_by_visible_text("Second Group")
        
        self.submit_form("merge_form")
        
        self.open_url('/group/list')
        self.assert_not_in_list_table("6th group")
        
        el = self.wd.find_element(By.LINK_TEXT, "Second Group")
        el.click()
        
        self.assert_num_rows(3)
    
    def test_merge_overlap(self):
        """ Test the group merge feature (overlap). """
        self.open_url('/group/list')
        
        el = self.wd.find_element(By.LINK_TEXT, "First Group")
        el.click()
        time.sleep(0.5)
        
        self.assert_num_rows(6)
        
        self.open_url('/group/list')
        self.wd.find_element(By.ID, "subnav-merge").click()
        time.sleep(0.5) # FIXME: Need to figure out how to wait on page loads; this is supposed to happen automatically ...
        self.assertEquals('Merge Group', self.wd.title)
        
        sel = Select(self.wd.find_element(By.ID, "from_group_id"))
        sel.select_by_visible_text("6th group")
        
        sel = Select(self.wd.find_element(By.ID, "to_group_id"))
        sel.select_by_visible_text("First Group")
        
        self.submit_form("merge_form")
        
        self.open_url('/group/list')
        self.assert_not_in_list_table("6th group")
        
        el = self.wd.find_element(By.LINK_TEXT, "First Group")
        el.click()
        
        self.assert_num_rows(6)
        
    def test_delete_link_no_resources(self):
        """ Test clicking the delete link when no resources. (prompt) """
        g = groups.get_by_name("fifth group")
        
        self.open_url('/group/list')
        
        deletelink = self.wd.find_element(By.ID, "delete-link-{0}".format(g.id))
        deletelink.click()
        
        alert = self.wd.switch_to_alert()
        self.assertEqual("Are you sure you want to remove group {0} (id={1})".format(g.name, g.id), alert.text)
        alert.accept()
        
        self.assert_notification("Group deleted: {0} (id={1})".format(g.name, g.id))
        self.assert_not_in_list_table(g.name)
                
    def test_delete_link_resources(self):
        """ Test clicking the delete link with resources (confirm page) """
        g = groups.get_by_name("First Group")
        
        self.open_url('/group/list')
        
        deletelink = self.wd.find_element(By.ID, "delete-link-{0}".format(g.id))
        deletelink.click()
        
        self.assertEquals('Delete Group', self.wd.title)
        
        self.submit_form("delete_form")
        
        alert = self.wd.switch_to_alert()
        self.assertEqual("Are you sure you wish to permanently delete this group and specified resources?", alert.text)
        alert.accept()
        
        self.assert_notification("Group deleted: {0} (id={1})".format(g.name, g.id))
        self.assert_not_in_list_table(g.name)