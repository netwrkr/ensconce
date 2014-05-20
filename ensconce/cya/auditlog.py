"""
"""
import collections
import logging
import warnings
from datetime import datetime, timedelta

from sqlalchemy import and_, func, text

from ensconce import model
from ensconce.model import meta
from ensconce.webapp.util import operator_info
from ensconce.dao import SearchResults
from ensconce.autolog import log as applog

logger = lambda: logging.getLogger('AUDIT')

CODE_AUTH_FAILED = 'auth.failed'
CODE_AUTH_UNAUTHORIZED = 'auth.unauthorized'
CODE_AUTH_LOGIN = 'auth.login'
CODE_AUTH_LOGOUT = 'auth.logout'

CODE_CONTENT_VIEW = 'content.view'
CODE_CONTENT_MOD = 'content.mod'
CODE_CONTENT_ADD = 'content.add'
CODE_CONTENT_ARCH = 'content.arch'
CODE_CONTENT_DEL = 'content.del'

CODE_SEARCH = 'search'

def enumerate_codes():
    codes = []
    for k,v in globals().items():
        if k.startswith('CODE_'):
            codes.append(v)
    return codes

def log(code, target=None, comment=None, attributes_modified=None):
    """
    :param code: The auditlog code.
    :keyword target: The object being modified.
    :keyword comment: Any description of event that is not captured by other attributes (e.g. search string would go in here).
    :keyeword attributes_modified: Any object attributes being modified (if relevant).
    """
    if attributes_modified is None:
        attributes_modified = []
    
    session = meta.Session()
    
    try:
        entry = model.AuditlogEntry()
        entry.code = code
        entry.comment = comment
        entry.operator_id = operator_info().user_id
        entry.operator_username = operator_info().username 
        
        if target:
            entry.object_id = target.id
            entry.object_type = target.__class__.__name__
            if hasattr(target, 'label'):
                entry.object_label = target.label
        
        entry.attributes_modified = attributes_modified 
        
        session.add(entry)
        session.flush()
        
        build_msg = []
        
        build_msg.append("code={0}".format(code))
        if operator_info().username:
            build_msg.append('operator={0}'.format(operator_info().username))
        if target:
            build_msg.append('target={0}'.format(target))
        if attributes_modified:
            build_msg.append('modified={0}'.format(','.join(attributes_modified)))
        
        if comment:
            build_msg.append(comment)
        
        # For now we're just writing this to syslog, but probably we want a database 
        # log for this stuff too.
        logger().info(' '.join(build_msg))
    except:
        # This may be wrong, but otherwise we go to try to commit() in our wrapper and it fails due to 
        # an invalid session state.
        session.rollback()
        
        logger().critical("There was an error writing audit log: {code}, target={target}, mod={mod}".format(code=code,
                                                                                                       target=target,
                                                                                                       mod=attributes_modified), 
                          exc_info=True)
    
def search(start=None, end=None, operator_id=None, operator_username=None, code=None, 
           object_type=None, object_id=None, offset=None, limit=None,
           skip_count=False):
        
    session = meta.Session()
    
    try:
        a_t = model.auditlog_table
        q = session.query(model.AuditlogEntry)
        
        clauses = []
        if start:
            applog.debug("Filtering on start date: {0}".format(start))
            clauses.append(a_t.c.datetime >= start)
            
        if end:
            applog.debug("Filtering on end date: {0}".format(end))
            clauses.append(a_t.c.datetime <= end)
        
        if operator_id:
            if operator_username:
                warnings.warn("Ignoring operator_username parameter, since operator_id was specified.")
            clauses.append(a_t.c.operator_id == operator_id)
        elif operator_username:
            applog.debug("Filtering on username: {0}".format(operator_username))
            clauses.append(a_t.c.operator_username == operator_username)
        
        if object_type:
            applog.debug("Filtering on object type: {0}".format(object_type))
            clauses.append(a_t.c.object_type == object_type)
            
        if object_id:
            applog.debug("Filtering on object id: {0}".format(object_id))
            clauses.append(a_t.c.object_type == object_id)
        
        if code:
            applog.debug("Filtering on code: {0}".format(code))
            clauses.append(a_t.c.code.like(code)) # Allow for code wildcards (e.g. "content.%" to be passed in
        
        if not skip_count:
            count = session.query(func.count(a_t.c.id)).filter(and_(*clauses)).scalar()
        else:
            count = None
        
        applog.debug("Total number of rows: {0}".format(count))
        
        q = q.filter(and_(*clauses))
        
        q = q.order_by(a_t.c.datetime.desc())
        
        if offset and count > offset:
            q = q.offset(offset)
            
        if limit:
            q = q.limit(limit)
        
        #applog.debug("Auditlog query: {0}".format(q))
        
        results = q.all() 
    except:
        applog.exception("Error searching audit log.")
        raise
    
    return SearchResults(count, results)

def recent_content_views(operator_id, object_type, code=None, object_id=None, limit=10, limit_days=7, skip_count=False):
    """
    
    """
    # This is not very efficient yet.  The right way to do this is probably to 
    # map a subclass of AuditLogEntry to a query that groups by object_id, object_type, and code 
    # showing the max timestamp.
    
    session = meta.Session()
    
    try:
        a_t = model.auditlog_table
        subq = session.query(func.max(a_t.c.id)).group_by(a_t.c.object_type,
                                                          a_t.c.object_id,
                                                          a_t.c.code,
                                                          a_t.c.operator_id)
        
        clauses = []
        clauses.append(a_t.c.operator_id==operator_id)
        clauses.append(a_t.c.object_type==object_type)
        # In an attempt to improve efficiency:
        clauses.append(a_t.c.datetime>=datetime.now()-timedelta(days=limit_days))
        
        
        
        if object_id:
            clauses.append(a_t.c.object_id==object_id)
        
        if code:
            clauses.append(a_t.c.code==code)
        
        subq = subq.filter(and_(*clauses))
        
        # Now get all the actual audit log rows that match that.  Order by the datetime descending.
        q = session.query(model.AuditlogEntry).filter(a_t.c.id.in_(subq))
        q = q.order_by(a_t.c.datetime.desc())
        
        if not skip_count:
            count = q.count()
        else:
            count = 0 
        
        q = q.limit(limit)
        
        results = q.all() 
        
    except:
        applog.exception("Error searching audit log.")
        raise
    
    return SearchResults(count, results)