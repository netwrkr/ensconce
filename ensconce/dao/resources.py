"""
This module provides the database routines to manipulate resources.
"""
from __future__ import absolute_import

from sqlalchemy import or_, and_, func
from sqlalchemy.orm.exc import NoResultFound

#from ensconce.dao import groups
from ensconce.autolog import log
from ensconce.dao import SearchResults
from ensconce.model import meta
from ensconce import model, exc

def get(resource_id, assert_exists=True):
    """
    This function will return a resource object for the id specified.
    :param resource_id: The ID for resource to lookup.
    :param assert_exists: Whether to raise :class:`exc.exception if entity does not exist (avoid NPE later).
    :raise ensconce.exc.NoSuchEntity: If operator does not exist and assert_exists is True.
    :rtype: :class:`model.Operator`
    """
    session = meta.Session()
    try:
        resource = session.query(model.Resource).get(resource_id)
    except:
        log.exception("Error retrieving resource")
        raise
    
    if assert_exists and not resource:
        raise exc.NoSuchEntity(model.Resource, resource_id)
    
    return resource

def get_by_name(name, assert_single=True, assert_exists=True):
    """
    Gets the/a matching resource by name.  
    
    If assert_one is True, then exactly one resource will be returned and
    an exception will be raised if there are multiple.  
    
    Otherwise the first match will be returned (ordered conssitently by ID), or
    None if no match found.
    
    :param name: The name of the resource.
    :param assert_single: Whether to ensure that there is only one match in the DB.
    :param assert_exists: Whether to ensure that there is a (at least one) match in the DB.
    :return: The matching resource, or None if no resource matches.
    """
    session = meta.Session()
    match = None
    try:
        r_t = model.resources_table
        q = session.query(model.Resource).filter_by(name=name)
        q = q.order_by(r_t.c.id)
        
        if assert_single:
            match = q.one()
        else:
            match = q.first()
            
    except NoResultFound:
        # Pass-through to check after block
        pass
    except:
        log.exception("Error looking up resource by name: {0}".format(name))
        raise
    
    if assert_exists and not match:
        raise exc.NoSuchEntity(model.Resource, name)
    return match


def search(searchstr=None, order_by=None, offset=None, limit=None): # @ReservedAssignment
    """
    Search within resources and return matched results for specified limit/offset.
    
    :param searchstr: A search string that will be matched against name, addr, and description attributes.
    :type searchstr: str
    
    :param order_by: The sort column can be expressed as a string that includes asc/desc (e.g. "name asc").
    :type order_by: str
    
    :param offset: Offset in list for rows to return (supporting pagination).
    :type offset: int
    
    :param limit: Max rows to return (supporting pagination).
    :type limit: int
    
    :returns: A :class:`ensconce.dao.SearchResults` named tuple that includes count and list of :class:`ensconce.model.Resource` matches.
    :rtype: :class:`ensconce.dao.SearchResults`
    """
    session = meta.Session()
    try:
        r_t = model.resources_table
        
        if order_by is None:
            order_by = r_t.c.name
        
        clauses = []
        
        if searchstr:
            clauses.append(or_(r_t.c.name.ilike('%'+searchstr+'%'),
                             r_t.c.addr.ilike('%'+searchstr+'%'),
                             r_t.c.description.ilike('%'+searchstr+'%')))
        
        # (Well, there's only a single clause right now, so that's a little over-engineered)
        
        count = session.query(func.count(r_t.c.id)).filter(and_(*clauses)).scalar()
        
        q = session.query(model.Resource).filter(and_(*clauses)).order_by(order_by)
        
        if limit is not None:
            q = q.limit(limit)
        if offset is not None:
            q = q.offset(offset)
        
        return SearchResults(count=count, entries=q.all())
    except:
        log.exception("Error listing resources")
        raise
    
def list(): # @ReservedAssignment
    """
    This function will return a list of all resources.
    
    :param offset: Offset in list for rows to return (supporting pagination).
    :type offset: int
    
    :param limit: Max rows to return (supporting pagination).
    :type limit: int
    
    :returns: A list of :class:`ensconce.model.Resource` results.
    :rtype: list
    """
    session = meta.Session()
    try:
        r_t = model.resources_table
        q = session.query(model.Resource)
        q = q.order_by(r_t.c.name)
        
        resources = q.all()
    except:
        log.exception("Error listing resources")
        raise
    else:
        return resources
    
def create(name, group_ids, addr=None, description=None, notes=None, tags=None):
    """
    This function will create a new resource record in the database.
    """
    if group_ids is None:
        group_ids = []
    elif isinstance(group_ids, (int, basestring)):
        group_ids = [int(group_ids)]
        
    if not group_ids:
        raise ValueError("No group ids specified for new resource.")
    
    session = meta.Session()
    
    try:
        resource = model.Resource()
        resource.name = name # BTW, non-unique resource names are allowed.
        resource.addr = addr
        resource.description = description
        resource.notes_decrypted = notes
        resource.tags = tags
        
        session.add(resource)
        session.flush()
    except:
        log.exception("Error creating resource.")
        raise

    for group_id in group_ids:
        try:
            group_lookup = model.GroupResource()
            group_lookup.resource_id = resource.id
            group_lookup.group_id = int(group_id)
            session.add(group_lookup)
            session.flush() # Fail fast
        except:
            log.exception("Error adding group to resource: {0}, resource={1}".format(group_id, name))
            raise
        
    session.flush()
    
    return resource

def modify(resource_id, group_ids=None, **kwargs):
    """
    This function will modify a resource entry in the database, only updating
    specified attributes.
    
    :param resource_id: The ID of resource to modify.
    :keyword group_ids: The group IDs that this resource should belong to.
    :keyword name: The resource name.
    :keyword addr: The resource address.
    :keyword notes: An (encrypted) notes field.
    :keyword tags: The tags field.
    :keyword description: A description fields (not encrypted).
    """
    if isinstance(group_ids, (basestring,int)):
        group_ids = [int(group_ids)]
    
    if group_ids is not None and len(group_ids) == 0:
        raise ValueError("Cannot remove all groups from a resource.")
    
    session = meta.Session()
    
    resource = get(resource_id)
    
    update_attributes = kwargs
    
    try:
        modified = model.set_entity_attributes(resource, update_attributes, encrypted_attributes=['notes'])
        session.flush()
    except:
        log.exception("Error updating resource.")
        raise
    
    gr_t = model.group_resources_table
    
    if group_ids is not None:
        # Is it different from what's there now?
        if set(group_ids) != set([cg.id for cg in resource.groups]):
            try:
                session.execute(gr_t.delete(gr_t.c.resource_id==resource_id))
                for group_id in group_ids:
                    group_id = int(group_id)
                    gr = model.GroupResource()
                    gr.resource_id = resource.id
                    gr.group_id = group_id
                    session.add(gr)
                session.flush()
            except:
                log.exception("Error adding group memberships")
                raise
            else:
                modified += ['group_ids']
    
    session.flush()
    
    return (resource, modified)

def delete(resource_id):
    """
    This function will delete a host record from the database.
    """
    session = meta.Session()
    try:
        resource = get(resource_id)
        session.delete(resource)
        session.flush()
    except:
        log.exception("Error deleting resource: {0}".format(resource_id))
        raise
    return resource
