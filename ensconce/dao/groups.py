from __future__ import absolute_import
from datetime import datetime

import pytz
from sqlalchemy import and_, select
from sqlalchemy.orm.exc import NoResultFound

from ensconce import model, exc
from ensconce.model import meta
from ensconce.autolog import log
#from ensconce.dao import history

def get(group_id, assert_exists=True):
    """
    This function will return the group object for specified ID.
    
    :param password_id: The ID for operator to lookup.
    :param assert_exists: Whether to raise exception if entity does not exist (avoid NPE later).
    :rtype: :class:`ensconce.model.Group`
    :raise ensconce.exc.NoSuchEntity: If group does not exist and assert_exists is True.
    """
    session = meta.Session()
    try:
        group = session.query(model.Group).get(group_id)
    except:
        log.exception("Error retrieving group: {0}".format(group_id))
        raise

    if assert_exists and not group:
        raise exc.NoSuchEntity(model.Group, group_id)
    
    return group

def get_by_name(name, assert_exists=True):
    """
    Lookup form by (unique) name.
    :param name
    :param assert_exists: Whether to raise exception if entity does not exist (avoid NPE later).
    :rtype: :class:`ensconce.model.Group`
    :raise ensconce.exc.NoSuchEntity: If group does not exist and assert_exists is True.
    """
    group = None
    session = meta.Session()
    try:
        group = session.query(model.Group).filter_by(name=name).one()
    except NoResultFound:
        if assert_exists:
            raise exc.NoSuchEntity(model.Group, name)
    return group
    
def list(): # @ReservedAssignment
    """
    This function will query the database, and return a list of all
    of the defined groups.

    Returns a list of [group_id, group_name] lists, one for each group
    defined in the database.
    """
    session = meta.Session()
    try:
        gt = model.groups_table
        groups = session.query(model.Group).order_by(gt.c.name).all()
    except:
        log.exception("Error retrieving groups.")
        raise
    else:
        return groups

def create(name):
    """
    This function will create a group, add it to the database, and
    return the group_id of the newly created group.
    """
    session = meta.Session()
    try:
        group = model.Group()
        group.name = name
        session.add(group)
        session.flush()    
    except:
        log.exception("Error creating group: {0}".format(name))
        raise
    
    return group

def modify(group_id, **kwargs):
    """
    This function will update a group record in the database.
    
    :keyword name: The group name.
    :raise ValueError: If the group ID cannot be resolved.
    """
    session = meta.Session()
    group = get(group_id)
    update_attributes = kwargs
    try:
        modified = model.set_entity_attributes(group, update_attributes)
        session.flush()
    except:
        log.exception("Error updating group: {0}".format(group_id))
        raise
    
    return (group, modified)

def merge(from_group_id, to_group_id):
    """
    Merges all resources from one group into another and deletes the empty 'from' group afterwards.
    
    :param from_group_id: The group to merge from (will be removed when finished).
    :type from_group_id: int
    :param to_group_id: The group to merge resources into.
    :type to_group_id: int 
    :returns: A tuple of the moved resources [list], the from (deleted) group, and the target group.
    :rtype: tuple 
    """
    session = meta.Session()
    from_group = get(from_group_id)
    to_group = get(to_group_id)
    try:
        # Keep track of the resources we are moving (this is just for auditing)
        moved_resources = from_group.resources.all()
        gr_t = model.group_resources_table
        
        # First we will remove any mapping rows that will conflict.
        del_stmt = gr_t.delete().where(and_(gr_t.c.group_id==from_group.id,
                                            gr_t.c.resource_id.in_(select([gr_t.c.resource_id]).where(gr_t.c.group_id==to_group.id))))
        session.execute(del_stmt)
        
        # Then move over remaining rows to the new gruop
        upd_stmt = gr_t.update().where(gr_t.c.group_id==from_group.id).values(group_id=to_group.id)
        session.execute(upd_stmt)
        
        # And finally delete the old group
        session.delete(from_group)
        
        # This should ensure that the group.resources collection will subsequently
        # return the right stuff (even if it was executed prior to our SQL above)
        session.flush()
    except:
        log.exception("Error merging group {0!r} to {1!r}".format(from_group, to_group))
        raise
        
    return (moved_resources, from_group, to_group)

def delete(group_id):
    """
    This function will remove a group from the database.
    """
    session = meta.Session()
    group = get(group_id)
    try:
        session.delete(group)
        session.flush()
    except:
        log.exception("Error removing group: {0}".format(group_id))
        raise
    
    return group