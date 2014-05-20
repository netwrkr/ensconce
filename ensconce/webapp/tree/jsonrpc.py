from __future__ import absolute_import
import socket
from functools import wraps

import cherrypy

from ensconce import search, acl, exc
from ensconce.cya import auditlog
from ensconce.auth import get_configured_providers
from ensconce.autolog import log
from ensconce.dao import groups, passwords, operators, resources
from ensconce.webapp.tree import expose_all
from ensconce.util.cpjsonrpc import JsonRpcMethods
from ensconce.util.pwtools import generate_password
 
# FIXME: Add the check_acl lines

def api_auth(f):
    @wraps(f)
    def wrapped(self, *args, **kwargs):
        user = operators.get_by_username(cherrypy.request.login)
        cherrypy.session['username'] = user.username # @UndefinedVariable
        cherrypy.session['user_id'] = user.id # @UndefinedVariable
        return f(self, *args, **kwargs)
    return wrapped

@expose_all(auth_decorator=api_auth)
class Root(JsonRpcMethods):
    
    @acl.require_access(acl.GROUP_R)
    def listGroups(self):
        return [g.to_dict() for g in groups.list()]
    
    @acl.require_access(acl.GROUP_R)    
    def getGroup(self, group_id):
        try:
            group_id = int(group_id)
        except ValueError:
            group = groups.get_by_name(group_id)
        else:
            group = groups.get(group_id)
        auditlog.log(auditlog.CODE_CONTENT_VIEW, target=group)
        return group.to_dict(include_resources=True)
        
    @acl.require_access(acl.RESOURCE_R)
    def getResource(self, resource_id):
        try:
            resource_id = int(resource_id)
        except ValueError:
            resource = resources.get_by_name(resource_id, assert_single=True)
        else:
            resource = resources.get(resource_id)
        auditlog.log(auditlog.CODE_CONTENT_VIEW, target=resource)
        return resource.to_dict(decrypt=True, include_passwords=True)
    
    @acl.require_access(acl.PASS_R)
    def getPassword(self, password_id, include_history=False):
        """
        Get the specified password record (decrypted) and optionally password history.
        
        :param password_id: The ID of password to lookup.
        :type password_id: int
        :param include_history: Whether to include history (previous passwords) for this password.
        :type include_history: bool
        """
        pw = passwords.get(password_id)
        auditlog.log(auditlog.CODE_CONTENT_VIEW, target=pw)
        return pw.to_dict(decrypt=True, include_history=include_history)
    
    @acl.require_access(acl.PASS_R)
    def getPasswordForResource(self, username, resource_id, include_history=False):
        """
        Looks up a password matching specified username @ specified resource name (e.g. hostname).
        
        :param username: The username associated with the password.
        :type username: str
        :param resource_id: The resource ID or name that we are looking up.
        :type resource_id: int or str
        :param include_history: Whether to include history (previous passwords) for this password.
        :type include_history: bool
        :return: The matching password, or None if none found.
        """
        try:
            try:
                resource_id = int(resource_id)
            except ValueError:
                resource = resources.get_by_name(resource_id, assert_single=True)
            else:
                resource = resources.get(resource_id)
            pw = passwords.get_for_resource(username=username, resource_id=resource.id, assert_exists=True)
            auditlog.log(auditlog.CODE_CONTENT_VIEW, target=pw)
            return pw.to_dict(decrypt=True, include_history=include_history)
        except exc.NoSuchEntity:
            log.info("Unable to find password matching user@resource: {0}@{1}".format(username, resource_id))
            raise
        except:
            log.exception("Unable to find password for resource.")
            raise RuntimeError("Unhandled error trying to lookup password for user@resource: {0}@{1}".format(username, resource_id))
    
    @acl.require_access(acl.GROUP_W)  
    def createGroup(self, name):
        """
        Create a new group with specified name.
        
        :param name: The new group name.
        :type name: str
        
        :return: The created group object.
        :rtype: dict
        """
        group = groups.create(name)
        auditlog.log(auditlog.CODE_CONTENT_ADD, target=group)
        return group.to_dict()
    
    @acl.require_access(acl.GROUP_W)
    def modifyGroup(self, group_id, name):
        """
        Modify (rename) a group.

        :param group_id: The ID of group to modify.
        :type group_id: int
        
        :keyword name: The new name of the group.
        :type name: str
        
        :return: The updated group object.
        :rtype: dict
        """
        (group, modified) = groups.modify(group_id, name=name)
        auditlog.log(auditlog.CODE_CONTENT_MOD, target=group, attributes_modified=modified)
        return group.to_dict()
            
    @acl.require_access(acl.RESOURCE_W)    
    def createResource(self, group_ids, name, addr=None, description=None, notes=None):
        """
        Creates a new resource, adding to specified groups.
        
        :param group_ids: The group IDs associated with this password.
        :type group_ids: list
        
        :keyword name:
        :keyword addr:
        :keyword description:
        :keyword notes: The notes field (will be encrypted).
        
        :return: The created resource object.
        :rtype: dict
        """
        resource = resources.create(name=name, group_ids=group_ids, addr=addr,
                                    description=description, notes=notes)
        auditlog.log(auditlog.CODE_CONTENT_ADD, target=resource)
        return resource.to_dict()
    
    @acl.require_access(acl.RESOURCE_W)
    def modifyResource(self, resource_id, **kwargs):
        """
        Modify an existing resource.
        
        This method requires keyword arguments and so only works with JSON-RPC2 protocol.

        :param resource_id: The identifier for the existing resource.
        :type resource_id: int
        
        :keyword name:
        :keyword addr:
        :keyword group_ids:
        :keyword notes:
        :keyword description:
        
        :return: The modified resource object.
        :rtype: dict
        """
        (resource, modified) = resources.modify(resource_id, **kwargs)
        auditlog.log(auditlog.CODE_CONTENT_MOD, target=resource, attributes_modified=modified)
        return resource.to_dict()
    
    @acl.require_access(acl.PASS_W)
    def createPassword(self, resource_id, username, password, description=None, expire_months=None):
        """
        Creates a new password for specified resource.
        
        :param resource_id: The resource with which to associate this password.
        :type resource_id: int
        
        :keyword: username:
        :keyword: password:
        :keyword: description:
        :keyword: expire_months:
        
        :return: The created password object.
        :rtype: dict    
        """
        pw = passwords.create(username, resource_id=resource_id, description=description, 
                              password=password, expire_months=expire_months)
        auditlog.log(auditlog.CODE_CONTENT_ADD, target=pw)
        return pw.to_dict()
    
    @acl.require_access(acl.PASS_W)
    def modifyPassword(self, password_id, **kwargs):
        """
        Modify an existing password.
        
        This method requires keyword arguments and so only works with JSON-RPC2 protocol.
        
        :param password_id: The ID of the password to modify.
        :type password_id: int
        
        :keyword username:
        :keyword password:
        :keyword description:
        
        :return: The modified password object.
        :rtype: dict
        """
        (pw, modified) = passwords.modify(password_id, **kwargs)
        auditlog.log(auditlog.CODE_CONTENT_MOD, target=pw, attributes_modified=modified)
        return pw.to_dict()
    
    def generatePassword(self, length=12, ascii_lower=True, ascii_upper=True, punctuation=True, 
                         digits=True, strip_ambiguous=True, strip_dangerous=True):
        """
        Generates a random password and returns this to the client.
        
        (No database information is updated or revealed by this method.)
        
        :param length: Length of generated password.
        :type length: int
        
        :param ascii_lower: Whether to include ASCII lowercase chars.
        :type ascii_lower: bool
        
        :param ascii_upper: Whether to include ASCII uppercase chars.
        :type ascii_upper: bool
        
        :param punctuation: Whether to include punctuation.
        :type punctuation: bool
        
        :param strip_ambiguous: Whether to remove easily-confused (LlOo0iI1) chars 
                                from the password.
        :type strip_ambiguous: bool
        :param strip_dangerous: Whethr to remove some of the more 'dangerous' punctuation 
                                (e.g. quotes) from the generated password.
        :type strip_dangerous: bool
        :returns: The generated password.
        :rtype: str
        """
        return generate_password(length=length, ascii_lower=ascii_lower, ascii_upper=ascii_upper,
                                 punctuation=punctuation, digits=digits, 
                                 strip_ambiguous=strip_ambiguous, strip_dangerous=strip_dangerous)
        
    @acl.require_access([acl.GROUP_R, acl.PASS_R, acl.RESOURCE_R, acl.USER_R])
    def search(self, searchstr):
        """
        Perform a search for specified search string.
        
        :param searchstr: A string to match (exactly).
        :type searchstr: str
        :returns: A dict like {'resources': [r1,r2,...], 'groups': [g1,g2,...], 'passwords': [p1,p2,...]}
        :rtype: dict
        """
        results = search.search(searchstr)
        auditlog.log(auditlog.CODE_SEARCH, comment=searchstr)
        return {
            'resources':    [r.to_dict(decrypt=False) for r in results.resource_matches],
            'groups':       [r.to_dict() for r in results.group_matches],
            'passwords':    [r.to_dict(decrypt=False) for r in results.password_matches],
        }
    
    @acl.require_access([acl.GROUP_R, acl.PASS_R, acl.RESOURCE_R, acl.USER_R])
    def tagsearch(self, tags):
        """
        Perform a search for specified tags (only).
        
        :param tags: A list of tags to search for (and).
        :type tags: list
        :returns: A dict like {'resources': [r1,r2,...], 'passwords': [p1,p2,...]}
        :rtype: dict
        """
        results = search.tagsearch(tags)
        auditlog.log(auditlog.CODE_SEARCH, comment=repr(tags))
        return {
            'resources':    [r.to_dict(decrypt=False) for r in results.resource_matches],
            'passwords':    [r.to_dict(decrypt=False) for r in results.password_matches],
        }
    
    @acl.require_access(acl.PASS_W)
    def deletePassword(self, password_id):
        """
        Delete a password (and all password history).
        
        :param password_id: The numeric ID of password.
        :type password_id: int
        :return: The deleted password object.
        :rtype: dict
        """
        pw = passwords.delete(password_id)
        auditlog.log(auditlog.CODE_CONTENT_DEL, target=pw)
        return pw.to_dict(decrypt=False)
        
    @acl.require_access(acl.RESOURCE_W)
    def deleteResource(self, resource_id):
        """
        Delete a resource (resource must be empty or error will be thrown).
        
        :param resource_id: The numeric ID of resource (cannot use resource name here).
        :type resource_id: int
        :return: The deleted resource object.
        :rtype: dict
        """
        r = resources.delete(resource_id)
        auditlog.log(auditlog.CODE_CONTENT_DEL, target=r)
        return r.to_dict(decrypt=False)
    
    @acl.require_access(acl.GROUP_W)
    def deleteGroup(self, group_id):
        """
        Delete a group (group must be empty or error will be thrown).
        
        :param group_id: The numeric ID of group (cannot use group name here).
        :type group_id: int
        :return: The deleted group object.
        :rtype: dict
        """
        g = groups.delete(group_id)
        auditlog.log(auditlog.CODE_CONTENT_DEL, target=g)
        return g.to_dict()
        