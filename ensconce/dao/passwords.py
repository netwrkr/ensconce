from __future__ import absolute_import

from datetime import datetime
from dateutil.relativedelta import relativedelta

import pytz

from sqlalchemy.sql import and_
from sqlalchemy.orm import attributes

from ensconce import model, exc
from ensconce.model import meta
from ensconce.autolog import log
from ensconce.webapp.util import operator_info

def get(password_id, assert_exists=True):
    """
    Returns the password object for specified ID.
    
    :param password_id: The ID for password to lookup.
    :param assert_exists: Whether to raise exception if entity does not exist (avoid NPE later).
    :rtype: :class:`model.Password`
    :raise ensconce.exc.NoSuchEntity: If password does not exist and assert_exists is True.
    """
    session = meta.Session()
    try:
        pw = session.query(model.Password).get(password_id)
    except:
        log.exception("Unable to retrieve password: {0}".format(password_id))
        raise
    
    if assert_exists and not pw:
        raise exc.NoSuchEntity(model.Password, password_id)
    
    return pw
    
def get_for_resource(username, resource_id, assert_exists=True):
    """
    Returns the password object for specified username and resource ID.
    
    :param username: The username for the password.
    :param resource_id: The resource ID.
    :param assert_exists: Whether to raise exception if entity does not exist (avoid NPE later).
    :rtype: :class:`model.Password`
    :raise ensconce.exc.NoSuchEntity: If password does not exist and assert_exists is True.
    """
    session = meta.Session()
    try:
        pw = session.query(model.Password).filter_by(username=username, resource_id=resource_id).first()
    except:
        log.exception("Unable to retrieve password: {0!r}".format((username, resource_id)))
        raise
    
    if assert_exists and not pw:
        raise exc.NoSuchEntity(model.Password, (username, resource_id))
    
    return pw

def delete(password_id):
    """
    This function will attempt to delete a operatorid from the database.
    """
    session = meta.Session()
    try:
        pw = get(password_id)
        session.delete(pw)
        session.flush()
    except:
        log.exception("Unable to delete password: {0}".format(password_id))
        raise
    
    return pw

def create(username, resource_id, password=None, description=None, tags=None, expire_months=None):
    """
    This function will create a operator_id record in the database.
    
    :rtype: :class:`ensconce.model.Password`
    """
    session = meta.Session()
    
    # --- This was removed, since this assumption seemed to be incorrect.
    # First, check to see if the given username exists for this resource
    #check = session.query(model.Password).filter_by(username=username, resource_id=resource_id).first()
    #if check:
    #    raise ValueError("Password with specified username already exists for resource: {0}, resource={1}".format(username, resource_id))
        
    if username is None or username == '':
        raise ValueError("No username specified")
    
    if resource_id is None or resource_id == '':
        raise ValueError("No resource_id specified")
    
    session = meta.Session()
    try:
        pw = model.Password()
        pw.username = username
        pw.resource_id = resource_id
        pw.password_decrypted = password
        pw.description = description
        pw.tags = tags
        pw.date_created = datetime.now(tz=pytz.utc)
        
        if expire_months is None: 
            pw.expire = None
        else:    
            pw.expire = datetime.now(tz=pytz.utc) + relativedelta(months=expire_months)
            
        session.add(pw)
        session.flush()
    except:
        log.exception("Error saving new password.")
        raise
    
    return pw

def modify(password_id, **kwargs):
    """
    This function will attempt to modify the pw with the passed
    in values.
    :param password_id: The ID of the entity to update.
    :keyword username: The username for the password.
    :keyword password: The (plaintext) password to set.
    :keyword description: A description for the password.
    :keyword expire_months: Integer number of months to expiration of password.
    :keyword tags: A tags field for the password.
    :return: A tuple including the modified object and a list of modified attributes.
    :raise ValueError: If password cannot be retrieved.
    """
    session = meta.Session()
    update_attributes = kwargs # Just to make it clearer
    try:
        pw = get(password_id)
        original_password = pw.password_decrypted # keep a copy for history sake
        modified = model.set_entity_attributes(pw, update_attributes, encrypted_attributes=['password'])
        
        if 'password' in  modified:
            # Store the old version of the password in password history with current modfiication time.
            prevpass = model.PasswordHistory()
            prevpass.password_decrypted = original_password
            prevpass.subject = pw
            # I hate having to pull in a webapp helper here, but not sure of a cleaner way to do this.
            prevpass.modifier_id = operator_info().user_id
            prevpass.modifier_username = operator_info().username
            log.debug("Password was modified, so saving password history: {0!r}".format(prevpass))
            session.add(prevpass)
             
        session.flush()
    except:
        log.exception("Error modifying password: {0}".format(password_id))
        raise
    
    return (pw, modified)