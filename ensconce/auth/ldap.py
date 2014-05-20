from __future__ import absolute_import
import re
import os.path

import ldap

from ensconce import exc
from ensconce.autolog import log
from ensconce.dao import operators
from ensconce.cya import auditlog

def provider_from_config(config):
    """
    Instantiates the provider class based on configuration.
    """
    return LdapProvider(url=config['ldap.url'],
                        basedn=config['ldap.basedn'],
                        start_tls=config['ldap.start_tls'],
                        userattr=config['ldap.userattr'],
                        userdn_pfx=config['ldap.userdn_pfx'],
                        groupdn_pfx=config['ldap.groupdn_pfx'],
                        binddn=config['ldap.binddn'],
                        bindpw=config['ldap.bindpw'],
                        cacert=config['ldap.cacert'],
                        cert=config['ldap.cert'],
                        key=config['ldap.key'],
                        authorized_groups=config['ldap.authorized_groups'])

class LdapProvider(object):
    
    def __init__(self, url, basedn, start_tls=True, userattr='uid', userdn_pfx=None,
                 groupdn_pfx=None, binddn=None, bindpw=None, 
                 cacert=None, cert=None, key=None, authorized_groups=None):
        self.url = url
        self.start_tls = start_tls
        self.basedn = basedn
        self.userdn_pfx = userdn_pfx
        self.groupdn_pfx = groupdn_pfx
        self.binddn = binddn
        self.bindpw = bindpw
        self.userattr = userattr
        self.cacert = cacert
        self.cert = cert
        self.key = key
        self.authorized_groups = authorized_groups
    
    @property
    def user_basedn(self):
        if self.userdn_pfx:
            return ','.join([self.userdn_pfx.rstrip(','), self.basedn])
        else:
            return self.basedn
    
    @property
    def group_basedn(self):
        if self.groupdn_pfx:
            return ','.join([self.groupdn_pfx.rstrip(','), self.basedn])
        else: 
            return self.basedn
    
    def authenticate(self, uid, password):
        """
        Attempt to authenticate user with specified username and password.
        
        This method raises a few specific exceptions related to authorization
        which calling code may use to provide more information (if desired)
        to the users.  (Other exceptions may be raised, which should also be
        safely handled by calling code.)
        
        :raise :class:`ensconce.exc.InvalidCredentials`: If username and/or password are invalid.
        :raise :class:`ensconce.exc.InsufficientPrivilege`: If required group membership is not satisified.
        """
        
        if self.cacert:
            # Check the paths, because python-ldap won't complain
            if not os.path.exists(self.cacert):
                raise exc.ConfigurationError("Unable to open cacert file: {0}".format(self.cacert))
            ldap.set_option(ldap.OPT_X_TLS_CACERTFILE, self.cacert) # @UndefinedVariable
        
        if self.cert:
            # Check the paths, because python-ldap won't complain
            if not os.path.exists(self.cacert):
                raise exc.ConfigurationError("Unable to open cert file: {0}".format(self.cert))
            if not self.key:
                raise exc.ConfigurationError("Certificate specified, but no private key specified.")
            if not os.path.exists(self.key):
                raise exc.ConfigurationError("Unable to open private key file: {0}".format(self.key))
            
            ldap.set_option(ldap.OPT_X_TLS_CERTFILE, self.cert) # @UndefinedVariable
            ldap.set_option(ldap.OPT_X_TLS_KEYFILE, self.key) # @UndefinedVariable
            
        con = ldap.initialize(self.url)
        
        if self.start_tls:
            try:
                con.start_tls_s()
            except:
                log.exception("Error initializing LDAP connection to {0}".format(self.url))
                raise
            
        userdn = None
        
        if self.binddn:
            try:
                con.simple_bind_s(self.binddn, self.bindpw )
            except ldap.INVALID_CREDENTIALS as ic: # @UndefinedVariable
                log.exception("Unable to bind to LDAP server using specified binddn/bindpw")
                raise
        
            filter = '({0}={1})'.format(self.userattr, uid)
            
            attrs = ['displayName', 'uidNumber']
            result = con.search_s(self.user_basedn, ldap.SCOPE_SUBTREE, filter, attrs) # @UndefinedVariable
            if result:
                userdn = result[0][0]
                # displayName = result[0][1]['displayName'][0]
                # uidNumber = result[0][1]['uidNumber'][0]
            else:
                log.error("User was not found: {0}".format(uid))
                raise exc.InvalidCredentials()
        else:
            userdn = '{0}={1},{2}'.format(self.userattr, uid, self.user_basedn)
            log.debug("Constructed DN from username: {0}".format(userdn))
            
        try:
            con.simple_bind_s(userdn, password)
        except ldap.INVALID_CREDENTIALS: # @UndefinedVariable
            log.exception("Invalid credentials.")
            raise exc.InvalidCredentials()
        
        # Do we need to check group memberships?
        if self.authorized_groups:
            attrs = ['cn', 'member']
            results = con.search_s(self.group_basedn, ldap.SCOPE_SUBTREE, '(&(objectclass=groupOfNames)(member={0}))'.format(userdn), attrs) # @UndefinedVariable
            dns = [r[0] for r in results]
            if not (set(dns) & set(self.authorized_groups)):
                log.debug("User's groups: {0!r}".format(set(dns)))
                log.debug("Authorized groups: {0!r}".format(set(self.authorized_groups)))
                log.error("User is not member of any of the allowed groups.")
                raise exc.InsufficientPrivileges() 
    
    def resolve_user(self, username):
        """
        Resolves the specified username to a database user, creating one if necessary.
        :rtype: :class:`ensconce.model.Operator` 
        """
        user = operators.get_by_username(username, assert_exists=False)
        if not user:
            user = operators.create(username=username, password=None, access_id=1, externally_managed=True)
            # FIXME: This access thing is very kludgy.
            auditlog.log(auditlog.CODE_CONTENT_ADD, target=user, comment="Operator created by LDAP authenticator.")
        return user
    
    def __str__(self):
        return 'ldap-auth-provider'
    
    def __repr__(self):
        return '<{0} url={1} basedn={2} start_tls={3}>'.format(self.__class__.__name__,
                                                               self.url,
                                                               self.basedn,
                                                               self.start_tls)
        