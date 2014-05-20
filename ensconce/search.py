from __future__ import absolute_import
import re
from collections import namedtuple

from sqlalchemy.sql import and_, or_

from ensconce import model
from ensconce.model import meta
from ensconce.autolog import log

SearchResults = namedtuple('SearchResults', ('resource_matches', 'group_matches', 'password_matches'))
TagSearchResults = namedtuple('TagSearchResults', ('resource_matches', 'password_matches'))

def search(searchstr, search_resources=True, search_groups=True, search_passwords=True, include_encrypted=False):
    """
    This function will search the database for all occurances of
    the search string in all applicable tables. It will return a list
    of lists of matches, one for resources, groups and passwords.
    
    :param searchstr: The search keyword (currently only single word supported)
    :param search_resources: Whether to search the resources table..
    :param search_groups: Whether to search the groups table.
    :param search_passwords: Whether to search the passwords table.
    :param include_encrypted: Whether to search through encrypted fields (will be slow!). This is currently only
                              the resources.notes field.
    :returns: A tuple of (resource matches, group matches, password matches)
    :rtype: :class:`ensconce.search.SearchResults`
    """
    
    resource_results = []
    group_results = []
    password_results = []
    
    session = meta.Session()
    if search_resources:
        r_t = model.resources_table
        try:
            q = session.query(model.Resource).filter(or_(r_t.c.name.ilike('%'+searchstr+'%'),
                                                     r_t.c.addr.ilike('%'+searchstr+'%'),
                                                     r_t.c.description.ilike('%'+searchstr+'%'),
                                                     r_t.c.tags.ilike('%'+searchstr+'%')))
            q = q.order_by(r_t.c.name)
            resource_results = q.all()
            
            if include_encrypted: 
                for r in session.query(model.Resource).all():
                    if r not in resource_results:
                        if r.notes_decrypted and searchstr.lower() in r.notes_decrypted.lower():
                            resource_results.append(r)
                            
                # re-sort them.
                resource_results = sorted(resource_results, key=lambda rsc: rsc.name)
                
        except:
            log.exception("Error searching on resources.")
            raise

    if search_groups:    
        try:
            g_t = model.groups_table
            q = session.query(model.Group).filter(g_t.c.name.ilike('%'+searchstr+'%'))
            q = q.order_by(g_t.c.name)
            group_results = q.all()
        except:
            log.exception("Error searching on groups.")
            raise
                   
    if search_passwords:
        try:
            p_t = model.passwords_table
            
            # And these are the users/passwords associated with resources
            q = session.query(model.Password).filter(or_(p_t.c.username.ilike('%'+searchstr+'%'),
                                                         p_t.c.description.ilike('%'+searchstr+'%'),
                                                         p_t.c.tags.ilike('%'+searchstr+'%')))
            q = q.order_by(p_t.c.username)
            pw_results = q.all()
            
            password_results.extend(pw_results)

        except:
            log.exception("Error searching on passwords.")
            raise

    return SearchResults(resource_results, group_results, password_results)


def tagsearch(tags, search_resources=True, search_passwords=True):
    """
    This function will search the database for all occurances of specified tags (AND)
    in the resources and passwords fields.
    
    :param tags: The list of tags to search for.
    :type tags: list
    :param search_resources: Whether to search the resources table..
    :param search_passwords: Whether to search the passwords table.
    :returns: A tuple of (resource matches, password matches)
    :rtype: :class:`ensconce.search.TagSearchResults`
    """    
    if isinstance(tags, basestring):
        tags = [tags]
        
    session = meta.Session()
    
    resource_results = []
    password_results = []
    
    def _process_tag(tag):
        tag = tag.strip()
        # Support prefixing or suffixing tags with ':'
        prefix = tag.startswith(':')
        suffix = tag.endswith(':')
        
        if prefix or suffix:
            tag = tag.strip(':')
        
        tag = re.escape(tag)
        
        if prefix:
            tag = '.+?\:' + tag
            
        if suffix:
            tag += '\:.+?'
        
        # Defnitely possible here to create something that won't match anything
        return tag
    
    if search_resources:
        r_t = model.resources_table
        try:
            r_clause = []
            for tag in tags:
                tagstr = _process_tag(tag)
                r_clause.append(r_t.c.tags.op('~*')(r'([^|[:alnum:]_-]|^){0}([^[:alnum:]_-]|$)'.format(tagstr)))
            
            q = session.query(model.Resource).filter(and_(*r_clause))
            q = q.order_by(r_t.c.name)
            resource_results = q.all()
            log.debug("Got these resource results: {0!r}".format(resource_results))
            
        except:
            log.exception("Error searching on resources.")
            raise
                   
    if search_passwords:
        try:
            p_t = model.passwords_table
            
            p_clause = []
            for tag in tags:
                tagstr = _process_tag(tag)
                p_clause.append(p_t.c.tags.op('~*')(r'([^|[:alnum:]_-]|^){0}([^[:alnum:]_-]|$)'.format(tagstr)))
            
            # And these are the users/passwords associated with resources
            q = session.query(model.Password).filter(and_(*p_clause))
            q = q.order_by(p_t.c.username)
            password_results = q.all()
            log.debug("Got these password results: {0!r}".format(password_results))
            
        except:
            log.exception("Error searching on passwords.")
            raise

    return TagSearchResults(resource_results, password_results)
