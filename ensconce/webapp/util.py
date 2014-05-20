"""
Common webapp utility functions/classes.
"""
import warnings
from collections import namedtuple
import json

import pkg_resources
import cherrypy
from cherrypy.process import plugins
from Crypto import Random

from jinja2 import Environment, PackageLoader, Markup
from wtforms import Form, SelectField

from ensconce.util import multidict
from ensconce.autolog import log
from ensconce.dao import groups
from ensconce.config import config

OperatorInfo = namedtuple('OperatorInfo', ('user_id', 'username'))

def escapejs(val):
    if isinstance(val, unicode):
        val = val.encode('utf-8')
    return json.dumps(Markup(val, encoding='utf-8').unescape().encode('utf-8'))

class QuickGroupForm(Form):
    group_id = SelectField('Group', coerce=int)
    
def render(filename, data=None):
    """
    Convenience method to render a template.
    """
    from ensconce import acl
    
    if data is None:
        data = {}
    
    data['title_prefix'] = config.get('ui.title_prefix')
    data['operator_info'] = operator_info()
    
    env = Environment(loader=PackageLoader('ensconce', 'templates'),
                      autoescape=True,
                      finalize=lambda x: '' if x is None else x)
    env.globals['pop_notifications'] = pop_notifications
    
    # Expose the ACL module so that there can be some checking in the templates 
    # (to avoid showing buttons that won't be clickable)
    env.globals['acl'] = acl
    
    try:
        env.globals['app_version'] = pkg_resources.get_distribution("ensconce").version
    except:
        log.exception("Error determining software version.")
        env.globals['app_version'] = '?.?'
    
    # Add an escape filter for when we need to embed values in JS code. 
    env.filters['escapejs'] = escapejs
    
    if operator_info().user_id: # They are logged in, so add the quick-group-nav form.
        form = QuickGroupForm() # Do not initialize we/ request params, since that could be confusing.
        form.group_id.choices = [(0, '[Jump to Group]')] + [(g.id, g.name) for g in groups.list()]
        env.globals['quickgroupform'] = form
    
    return env.get_template(filename).render(data)

def notify(message):
    """
    Pushes a notification messages onto the user's session.
    :param message: str
    """
    try:
        if isinstance(message, unicode):
            message = message.encode('utf8')
        try:
            notifications = cherrypy.session['notifications'] # @UndefinedVariable
        except KeyError:
            cherrypy.session['notifications'] = notifications = [] # @UndefinedVariable
            
        notifications.append(message)
    except:
        # Do *not* make notification rollback our transaction.
        log.exception("Unable to add notification.")
        pass

def notify_entity_activity(entity, activity):
    """
    Convenience method to push a (consistent) "<Entity> created" message to notification
    queue.
    :param entity: The entity that has been created.
    :type entity: :class:`ensconce.model.Entity`
    :param event: The activitiy performed on entity (created/updated/deleted).
    """
    try:
        if activity not in ('created', 'updated', 'deleted', 'archived'):
            warnings.warn("Unexpected activity: {0}".format(activity))
        notify('{entity} {activity}: {label} (id={id})'.format(entity=entity.__class__.__name__,
                                                               activity=activity,
                                                               label=entity.label,
                                                               id=entity.id))
    except:
        # Do *not* make notification rollback our transaction.
        log.exception("Unable to add entity notification.")
        pass
    
def pop_notifications():
    """
    Removes and returns all notification messages from current user's session.
    :rtype: list
    """
    notifications = cherrypy.session.get('notifications') # @UndefinedVariable
    if notifications is None:
        notifications = []
    cherrypy.session['notifications'] = [] # @UndefinedVariable
    return notifications
 
def operator_info():
    """
    Gets the user ID and username for currently logged-in user -- or None,None 
    if no user is logged in.
    
    :rtype: `class`:OperatorInfo
    """
    try:
        user_id = cherrypy.session.get('user_id') # @UndefinedVariable
        username = cherrypy.session.get('username') # @UndefinedVariable
    except AttributeError:
        user_id = None
        username = None
    return OperatorInfo(user_id, username)

def request_params(params=None):
    """
    Creates a MultiDict using the cherrypy request params suitable for use
    in wtforms.Form instances.
    :param params: An optional explicit dict of params, by default will use cherrypy.request.params
    :rtype: :class:`ensconce.util.multidict.MultiDict`
    """
    if params is None:
        params = cherrypy.request.params
    
    # Iterate over params; if any of the values are list/tuple values, we need to explode this
    # out.
    # 
    # I know there is a much more elegant way to do this; I'll think about it later.
    normalized = []
    for (k,v) in params.items():
        if isinstance(v, (list,tuple)):
            normalized.extend(zip([k] * len(v), v))
        else:
            normalized.append((k,v))
        
    return multidict.MultiDict(normalized)


class RNGInitializer(plugins.SimplePlugin):
    """
    A cherrypy plugin that handles the initialization of the PyCrypto RNG after forking.
    
    From PyCrypto docs:
    
        Caveat: For the random number generator to work correctly, you must
        call Random.atfork() in both the parent and child processes after
        using os.fork()

    When we run the application via cherryd, forking is handled by the 
    :class:`cherrypy.process.plugins.Daemonizer` plugin, so we need to make sure
    we have a plugin that runs *after* that one that will run the 
    :method:`Crypto.Random.atfork` method.   
    """
    def start(self):
        log.debug("Re-initializing the RNG after any forking.")
        Random.atfork()
        
    start.priority = 99
