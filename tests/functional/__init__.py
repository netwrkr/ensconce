import os.path
import threading
import socket
import collections
import time

import configobj
import cherrypy
import requests
from cherrypy.process.servers import wait_for_free_port

import selenium.webdriver as webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from ensconce.config import init_app, config
from ensconce.autolog import log
from ensconce import server

from tests import BaseModelTest

__here__ = os.path.abspath(os.path.dirname(__file__))

DriverDetails = collections.namedtuple('DriverDetails', ["capabilities", "remote_host"])

def get_selenium_config():
    cfg = configobj.ConfigObj(os.path.join(__here__, 'settings.cfg'), interpolation='template')
    local_settings_path = os.path.join(__here__, 'local.settings.cfg')
    if os.path.exists(local_settings_path):
        cfg.merge(configobj.ConfigObj(local_settings_path, interpolation='template'))
    return cfg

def get_server_information():
    sel_config = get_selenium_config()
    server_scheme = sel_config.get('server_scheme', 'http')
    server_hostname = sel_config.get('server_hostname', socket.getfqdn())
    server_port = sel_config.get('server_port', config['server.socket_port'])
    return '{}://{}:{}'.format(server_scheme, server_hostname, server_port)

def get_configured_remote_drivers():
    """
    Get the relevant WebDriver information from the associated config files
    """
    sel_config = get_selenium_config()
    drivers = []
    for k, v in sel_config.iteritems():
        if not isinstance(v, configobj.Section):
            continue
        # all sections in this configuration file is interpreted as a webdriver
        # browser DesireCapabilities attribute with connection information
        drivers.append(DriverDetails(k, v['remote']))
    return drivers or [DriverDetails("Firefox", "unused")]


class FunctionalTestController(BaseModelTest):
    
    @classmethod
    def setUpClass(cls):
        super(FunctionalTestController, cls).setUpClass()
        
        #from ensconce import server_autoconfig
        
        if not server.configured:
            server.configure()
        
        assert 'db' in config['auth.provider'], "Need to have 'db' in providers list."
        assert not config['server.ssl_certificate'], "SSL isn't supported yet for functional tests."
        
        # This is done so that we get a nicer error message if the port is still in-use.
        # (CherryPy will just silently sys.exit())
        
        # Let's try using cherrypy's method directly.
        #if not check_port(config["server.socket_host"], config["server.socket_port"]):
        #    raise IOError("Port is not free: {0}:{1}".format(config["server.socket_host"], config["server.socket_port"]))
        #
        # Interestingly that fails ..
        
        wait_for_free_port(config["server.socket_host"], config["server.socket_port"], timeout=60) # net.ipv4.tcp_fin_timeout
        
#        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # http://www.unixguide.net/network/socketfaq/4.5.shtml
#        sock.bind((config["server.socket_host"], config["server.socket_port"]))
#        sock.close()
        
        cherrypy.engine.start()
        cherrypy.engine.wait(cherrypy.engine.states.STARTED)
        
    @classmethod
    def tearDownClass(cls):
        
        cherrypy.engine.stop()
        cherrypy.engine.wait(cherrypy.engine.states.STOPPED)
        
        #time.sleep(60) # Waiting for net.ipv4.tcp_fin_timeout seconds.  This is really hackish.
        
        super(FunctionalTestController, cls).tearDownClass()
        
    def setUp(self):
        super(FunctionalTestController, self).setUp()
        
    def tearDown(self):
        super(FunctionalTestController, self).tearDown()
        #self.server_thread.

    def url(self, *args, **kwargs):
        return get_server_information() + '/' + '/'.join(args)
    
    
class SeleniumTestController(FunctionalTestController):
    """
    Connect to the remote selenium webdriver to start running tests
    """
    driver = get_configured_remote_drivers()[0]
    required_ws_version = 13

    @classmethod
    def setUpClass(cls):
        super(SeleniumTestController, cls).setUpClass()
        try:
            wd = cls.get_webdriver()
        except:
            # addCleanup is an instance method; cannot be called from classmethods
            cls.tearDownClass()
            raise

        cls.wd = wd
        cls.initial_loads()
    
    @classmethod
    def get_webdriver(cls):
        exe = '{0}/wd/hub'.format(cls.driver.remote_host)
        cap = getattr(DesiredCapabilities, cls.driver.capabilities)
        log.debug("{0!r} {1!r}", exe, cap)
        return webdriver.Remote(command_executor=exe, desired_capabilities=cap)
    
    @classmethod
    def initial_loads(cls):
        cls.url_base = get_server_information()
        cls.wd.get(cls.url_base)
        cls.wd.set_window_size(1200, 800)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'wd'):
            log.debug("Quittting the WebDriver.")
            cls.wd.quit()
        super(SeleniumTestController, cls).tearDownClass()

    def fail_login(self, username, password):
        """
        Simple method to assure that login fails with specified creds.
        """
        self.wd.find_element_by_id("username").send_keys(username)
        self.wd.find_element_by_id("password").send_keys(password)
        self.wd.find_element_by_css_selector("button.submit").click() # implicit wait
        self.assert_form_error("Invalid username/password.")
        
    def login(self, username="op1", password="pw1"):
        self.wd.find_element_by_id("username").send_keys(username)
        self.wd.find_element_by_id("password").send_keys(password)
        self.wd.find_element_by_css_selector("button.submit").click() # implicit wait
        
        self.assertTrue(self.is_element_present(By.ID, "welcome"))
        welcome = self.wd.find_element(By.ID, "welcome")
        self.assertIn(username, welcome.text)
    
    def logout(self):
        # FIXME: click button
        self.wd.get(self.url_base + "/logout")
    
    def open_url(self, path):
        self.wd.get(self.url_base + path)

    def submit_form(self, form_id):
        self.wd.find_element_by_css_selector("#{0} button.submit".format(form_id)).click() # implicit wait
                
    def is_element_present(self, how, what):
        try:
            self.wd.find_element(by=how, value=what)
        except NoSuchElementException:
            return False
        return True
    
    def assert_num_rows(self, num_rows, table=None):
        if table is not None:
            xpath = "//table[{0}]".format(table)
        else:
            xpath = "//table"
        xpath += "/tbody/tr"
        elements = self.wd.find_elements(By.XPATH, xpath)
        self.assertEquals(num_rows, len(elements))
    
    def _assert_in_data_table(self, name, negate=False, row=1, is_link=False, table=1):
        if table is not None:
            xpath = "//table[{0}]".format(table)
        else:
            xpath = "//table"
        xpath += "/tbody/tr[{0}]/td".format(row)
        if is_link:
            xpath += "/a"
        
        elements = self.wd.find_elements(By.XPATH, xpath)
        names = [e.text for e in elements]
        if negate:
            self.assertNotIn(name, names)
        else:
            self.assertIn(name, names)
    
    def assert_in_data_table(self, name, row=1, is_link=False, table=1):
        self._assert_in_data_table(name=name, negate=False, row=row, is_link=is_link, table=table)
            
    def assert_not_in_data_table(self, name, row=1, is_link=False, table=1):
        self._assert_in_data_table(name=name, negate=True, row=row, is_link=is_link, table=table)
      
    def _assert_in_list_table(self, name, negate=False, column=1, is_link=True, nobr=False, table=None):
        if table is not None:
            xpath = "//table[{0}]".format(table)
        else:
            xpath = "//table"
        xpath += "/tbody/tr/td[{0}]".format(column)
        if nobr:
            xpath += '/nobr'
        if is_link:
            xpath += "/a"
        
        elements = self.wd.find_elements(By.XPATH, xpath)
        names = [e.text for e in elements]
        if negate:
            self.assertNotIn(name, names)
        else:
            self.assertIn(name, names)
    
    def assert_in_list_table(self, name, column=1, is_link=True, nobr=False, table=None):
        self._assert_in_list_table(name=name, negate=False, column=column, is_link=is_link, nobr=nobr, table=table)
            
    def assert_not_in_list_table(self, name, column=1, is_link=True, nobr=False, table=None):
        self._assert_in_list_table(name=name, negate=True, column=column, is_link=is_link, nobr=nobr, table=table)
        
    def assert_form_error(self, message):
        errors = self.wd.find_elements(By.CLASS_NAME, "form_error")
        error_messages = [e.text for e in errors]
        self.assertIn(message, error_messages)

    def assert_error_page(self):
        """
        Asserts that we got the generic 500 error page.
        """
        self.assertEquals("Unable to complete request", self.wd.title, "Expected 500 error page.")
        
    def assert_notification(self, msg):
        """
        Assert a specific notification message is present.
        """
        elements = WebDriverWait(self.wd, 5).until(lambda d: d.find_elements(By.XPATH, "//div[@class='notification']/span"))
        notifications = [e.text for e in elements]
        self.assertIn(msg, notifications)