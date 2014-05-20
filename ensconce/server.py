from __future__ import absolute_import

import os
import os.path
import json
import time
import pkgutil
import warnings
from datetime import datetime

import cherrypy
 
from cherrypy.wsgiserver.wsgiserver2 import CherryPyWSGIServer
from cherrypy.process.servers import ServerAdapter
# from cherrypy import _cperror, _cplogging


from ensconce import exc
from ensconce.config import config, init_app
from ensconce.autolog import log
from ensconce.model import meta
from ensconce.cya import auditlog
from ensconce.webapp import util, tree, tasks
from ensconce.auth import get_configured_providers

def error_handler(status, message, traceback, version):
    if cherrypy.request.headers.get('Accept') == 'application/json':
        return json.dumps({'error': {'code': status, 'message':message}})
    else:
        return util.render('error.html', {'status': status,
                                          'traceback': traceback,
                                          'message': message,
                                          'version': version})

# Kinda a kludge to capture that we really only want to run configure() once
# (This is relevant for testing.)
configured = False

def configure():
    """
    Configures the cherrypy server (sets up the tree, cherrypy config, etc.).
    """
    global configured
    # Setup the session storage directory if it does not exist
    if config.get('sessions.on') and config.get('sessions.storage_type') == 'file':
        path = config['sessions.storage_path']
        if not os.path.exists(path):
            try:
                os.makedirs(path) # By default these will be 0777
            except:
                warnings.warn("Unable to create the session directory: {0}".format(path))
                  
    cherrypy.config.update({
        "server.socket_host": config['server.socket_host'],
        "server.socket_port": config['server.socket_port'],
        
        "checker.on": False,
        "log.screen": False,
        #"engine.autoreload_on": False,
        "engine.autoreload_on": config.as_bool("debug"),
        
        "tools.sessions.on": config.as_bool('sessions.on'),
        "tools.sessions.persistent": config.as_bool('sessions.persistent'),
        "tools.sessions.path": config['sessions.path'],
        "tools.sessions.timeout": config['sessions.timeout'],
        "tools.sessions.storage_type": config['sessions.storage_type'],
        "tools.sessions.storage_path": config['sessions.storage_path'],
        "tools.sessions.secure": config['sessions.secure'],

        "request.show_tracebacks": config.as_bool("debug"),
        "checker.on": False,
        "tools.caching.on": False,
        "tools.expires.on": True,
        "tools.expires.secs": 0,
        "tools.expires.force": True,
        "tools.log_headers.on": False,
        "engine.autoreload_on": config.as_bool("debug"),
        
        "tools.encode.on": True,
        "tools.encode.encoding": "utf8",
        
        "error_page.default": error_handler
        })
    
    if config['server.behind_proxy']:
        cherrypy.config.update({"tools.proxy.on": True})
    
    if config['server.ssl_certificate']:
        # Make this conditional so we can host behind apache?
        cherrypy.config.update({
        "server.ssl_certificate": config['server.ssl_certificate'],
        "server.ssl_private_key": config['server.ssl_private_key'],
        "server.ssl_certificate_chain": config['server.ssl_certificate_chain'],
        })
        
    
    def rollback_dbsession():
        log.info("Rolling back SA transaction.")
        session = meta.Session()
        session.rollback()
    
    def commit_dbsession():
        log.info("Committing SA transaction.")
        session = meta.Session()
        session.commit()
    
    cherrypy.tools.dbsession_rollback = cherrypy.Tool('before_error_response', rollback_dbsession)
    cherrypy.tools.dbsession_commit = cherrypy.Tool('on_end_resource', commit_dbsession)
    
    # This is a "flow-control" exception.       
    class _LoginFailed(Exception):
        pass
        
    # TODO: Refactor to combine with the ensconce.webapp.tree methods
    def checkpassword(realm, username, password):
        auth_providers = get_configured_providers()
        try:
            for auth_provider in auth_providers:
                try:
                    auth_provider.authenticate(username, password)
                except exc.InsufficientPrivileges:
                    # Fail fast in this case; we don't want to continue on to try other authenticators.
                    raise _LoginFailed()
                except exc.AuthError:
                    # Swallow other auth errors so it goes onto next authenticator in the list.
                    pass
                except:
                    # Other exceptions needs to get logged at least.
                    log.exception("Unexpected error authenticating user using {0!r}".format(auth_provider))
                else:
                    log.info("Authentication succeeded for username {0} using provider {1}".format(username, auth_provider))
                    break
            else:
                log.debug("Authenticators exhausted; login failed.")
                raise _LoginFailed()
        except _LoginFailed:
            auditlog.log(auditlog.CODE_AUTH_FAILED, comment=username)
            return False
        else:
            # Resolve the user using the *current value* for auth_provider (as that is the one that passed the auth.
            user = auth_provider.resolve_user(username)
            
            log.debug("Setting up cherrypy session with username={0}, user_id={1}".format(username, user.id))    
            cherrypy.session['username'] = username # @UndefinedVariable
            cherrypy.session['user_id'] = user.id # @UndefinedVariable
            
            auditlog.log(auditlog.CODE_AUTH_LOGIN)
            return True
        
    app_conf = {
        "/static": {
            "tools.staticdir.on": True,
            "tools.staticdir.dir": config['static_dir'],
            "tools.staticdir.index": "index.html"
        },
        "/jsonrpc": {
            'tools.auth_basic.on': True,
            'tools.auth_basic.realm': 'api',
            'tools.auth_basic.checkpassword': checkpassword,
        }
    }
    
    # Add a plugin that will run the Crypto.Random.atfork() method, since this must
    # be called after forking (and we run this as a daemon in production)
    util.RNGInitializer(cherrypy.engine).subscribe()


    # Wire up our daemon tasks
    background_tasks = []
    if config.get('sessions.on'):
        background_tasks.append(tasks.DaemonTask(tasks.remove_old_session_files, interval=60))
        
    if config.get('backups.on'):
        backup_interval = config['backups.interval_minutes'] * 60
        background_tasks.append(tasks.DaemonTask(tasks.backup_database, interval=backup_interval, wait_first=True))
        background_tasks.append(tasks.DaemonTask(tasks.remove_old_backups, interval=3600, wait_first=True)) # This checks a day-granularity interval internally.
    
    
    # Unsubscribe anything that is already there, so that this method is idempotent
    # (This surfaces as nasty bugs in testing otherwise.)
    for channel in cherrypy.engine.listeners:
        for callback in cherrypy.engine.listeners[channel]:
            log.debug("Unsubscribing {0}:{1!r}".format(channel, callback))
#            log.debug("Unsubscribing {0}:{1!r}".format(channel, callback))
#            cherrypy.engine.unsubscribe(channel, callback)
        
    
    for task in background_tasks:
        cherrypy.engine.subscribe("start", task.start, priority=99)
        cherrypy.engine.subscribe("stop", task.stop)
    
    # Setup the basic/top-level webapp API
    root = tree.Root()
    
    # Iterate over all the modules in the ensconce.webapp.tree package and add
    # their 'Root' classes to the tree
    pkgpath = os.path.dirname(tree.__file__)
    for modname in [name for (_, name, _) in pkgutil.iter_modules([pkgpath])]:
        module = __import__("ensconce.webapp.tree." + modname, fromlist=["Root"])
        module_root = module.Root()
        setattr(root, modname, module_root)
    
    # I think this is here because we want to explicitly specify the ServerAdapter below
    # rather than use a default one.
    cherrypy.server.unsubscribe()
    
    app = cherrypy.tree.mount(root, "/", app_conf)
    app.log.error_log.level = cherrypy.log.error_log.level  # @UndefinedVariable
    app.log.access_log.level = cherrypy.log.access_log.level  # @UndefinedVariable
    
    addr = (config["server.socket_host"], config["server.socket_port"])
    server = CherryPyWSGIServer(addr, app, numthreads=50, timeout=2)  # TODO: make numthreads and keepalive timeout configurable
    
    
    # TODO: This is also mentioned in the cherrypy config above .... ?  One of these is probably redundant.
    server.ssl_certificate = config["server.ssl_certificate"]
    server.ssl_private_key = config["server.ssl_private_key"]
    if config["server.ssl_certificate_chain"]:
        server.ssl_certificate_chain = config["server.ssl_certificate_chain"]
        
    adapter = ServerAdapter(cherrypy.engine, server, server.bind_addr)
    adapter.subscribe()
    
    configured = True
    
def serve_forever():
    """
    Run the [already-configured] cherrypy server forever. 
    """
    cherrypy.engine.start()
    try:
        cherrypy.engine.block()
    except KeyboardInterrupt:
        log.info("shutting down due to KeyboardInterrupt")
        
def main():
    """
    Main entrypoint script, will initialize the application, configure server and serve (blocking).
    """
    init_app()
    configure()
    serve_forever()
    
if __name__ == u"__main__":
    main()
