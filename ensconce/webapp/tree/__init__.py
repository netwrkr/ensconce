import warnings
import math
import re
from functools import wraps
from collections import namedtuple
from datetime import datetime
import urllib

import pytz
import cherrypy
import gnupg
from jinja2 import Environment, PackageLoader
from dateutil import parser as date_parser
from wtforms import Form, TextField, PasswordField, validators, ValidationError, SelectField, IntegerField
from wtforms.ext.dateutil.fields import DateField

from ensconce.config import config
from ensconce.autolog import log
from ensconce.dao import operators
from ensconce import exc, search, acl
from ensconce.auth import get_configured_providers
from ensconce.crypto import state, util as crypto_util
from ensconce.model import meta, Password
from ensconce.cya import auditlog 
from ensconce.webapp.util import render, request_params, notify, operator_info
from wtforms.fields.simple import HiddenField

def _is_api_request():
    """
    Whether the request is for JSON data or initiated by XHR.
    """
    accept = cherrypy.request.headers.get('Accept')
    requested_with = cherrypy.request.headers.get('X-Requested-With')
    return accept in ('application/json',) or requested_with in ('XMLHttpRequest',) 
    
def ensure_initialized(f):
    """
    Makes sure crypto engine has been initialized.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not state.initialized:
            if config.get('debug', False) and config.get('debug.secret_key'):
                secret_key_file = config.get('debug.secret_key')
                crypto_util.load_secret_key_file(secret_key_file)
            else:        
                raise exc.CryptoNotInitialized("Crypto engine has not been initialized.")
        return f(*args, **kwargs)
    return wrapper

def transaction(f):
    """
    A decorator to automatically wrap the request in a single transaction.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        session = meta.Session()
        if not session.is_active:
            session.begin() # In case autocommit=True
        try:
            res = f(*args, **kwargs)
        except cherrypy.HTTPRedirect:
            # This is not a "real" exception, so we still want to commit the transaction.
            session.commit()
            raise
        except:
            log.exception("Rolling back SQLAlchemy transaction due to exception.")
            session.rollback()
            raise
        else:
            session.commit()
            return res
        
    return wrapper

def clean_errors(f):
    """
    Filter out or change specific exceptions and roll back transaction.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        sess = meta.Session()
        try:
            res = f(*args, **kwargs)
            # Unfortunately, that doesn't work flawlessly, since flush() will mark the session 'clean' despite it still being uncommitted
            # Also it doesn't capture things removed via SQL directly.  (But it's probably still worth keeping here.)
            if sess.new or sess.dirty or sess.deleted:
                warnings.warn("Unsaved objects in session will be discarded: new={0!r}, dirty={1!r}, deleted={2!r}".format(sess.new, sess.dirty, sess.deleted))
            return res
        except exc.NotLoggedIn:
            if not _is_api_request():
                current_url = cherrypy.url(qs=cherrypy.request.query_string, relative="server")
                if current_url and current_url != '/' and not re.search(r'logout/?$', current_url):
                    redirect_url = "/login?redirect={0}".format(urllib.quote_plus(current_url))
                else:
                    redirect_url = "/login"
                raise cherrypy.HTTPRedirect(redirect_url)
            else:
                raise cherrypy.HTTPError("403 Forbidden", "User is not logged in.")
        except exc.CryptoNotInitialized:
            sess.rollback()
            if not _is_api_request():
                raise cherrypy.HTTPRedirect("/startup")
            else:
                raise cherrypy.HTTPError("503 Service Unavailable", "Crypto engine has not been initialized.")
        finally:
            sess.close()
            
    return wrapper

def check_session(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'username' not in cherrypy.session: # @UndefinedVariable
            raise exc.NotLoggedIn()
        return f(*args, **kwargs)
    return wrapper

class expose_all(object):
    """
    A decorator to expose all methods and apply various other checks.
    """
    def __init__(self, insecure_methods=None, init_methods=None, auth_decorator=check_session):
        if insecure_methods is None:
            insecure_methods = []
        if init_methods is None:
            init_methods = []
            
        if init_methods:
            # If there are any init methods that are not insecure, we should issue a warning
            # (This is probably a misconfiguration.)
            candidates = set(init_methods).difference(set(insecure_methods))
            if candidates:
                warnings.warn("Some init_methods are not included in insecure_methods: {0}".format(candidates))
                
        self.insecure_methods = insecure_methods
        self.init_methods = init_methods
        self.auth_decorator = auth_decorator
        
    def __call__(self, clazz):
        for name, attr in clazz.__dict__.items():
            if hasattr(attr, "__call__"):
                attr.exposed = True
                if name not in self.init_methods:
                    #print("Adding ensure_initialized to {0}".format(name))
                    attr = ensure_initialized(attr)
                if name not in self.insecure_methods:
                    #print   ("Adding {0} to {1}.{2}".format(self.auth_decorator.__name__, clazz.__module__, name))
                    attr = self.auth_decorator(attr)
                    
                attr = transaction(attr) # Wrap entire request in SA transaction
                attr = clean_errors(attr) # Handle any exception cleanup
                
                setattr(clazz, name, attr) # Finally, replace the attr on the class
        return clazz

def validate_passphrase(form, field):
    """
    """
    try:
        passphrase = field.data
        key = crypto_util.derive_configured_key(passphrase)
        if not crypto_util.validate_key(key):
            raise ValidationError("Invalid passphrase entered.")
    except ValidationError:
        raise
    except exc.MissingKeyMetadata:
        log.exception("Missing key metadata.")
        raise ValidationError("Database crypto has not yet been initialized.") 
    except:
        log.exception("Error validating passphrase.")
        raise ValidationError("Error validating passphrase (see server logs).")
        
class PassphraseSubmitForm(Form):
    passphrase = TextField('Passphrase', validators=[validators.Required(),
                                                     validate_passphrase])

class LoginForm(Form):
    redirect = HiddenField('redirect')
    username = TextField('Username', validators=[validators.Required(),
                                                 validators.Length(max=255)])
    password = PasswordField('Password', validators=[validators.Required(),
                                                     validators.Length(max=2048)])

class AuditlogForm(Form):
    code = SelectField('Code', choices=[('', '(All)')]+[(c,c) for c in sorted(auditlog.enumerate_codes())], default='') # Need a default or we get coerced to u'None'
    start = DateField('Start')
    end = DateField('End')
    comment = TextField('Username')
    operator = TextField('Operator')
    page = IntegerField('Page', default=1)
    
    
@expose_all(insecure_methods=('login', 'startup', 'process_login', 'initialize', 'osd'),
            init_methods=('startup', 'initialize'))
class Root(object):
    """
    The root cherrypy handler class.
    """
    def index(self):
        
        # Grab some recent passwords accessed by the current user.
        results = auditlog.recent_content_views(operator_id=operator_info().user_id,
                                                object_type=Password.object_type(),
                                                limit=20,
                                                skip_count=True)
                    
        return render("index.html", {'recent_pw_views': results.entries})
    
    @cherrypy.tools.response_headers(headers=[('Content-Type', 'text/xml')])
    def osd(self):
        return render("osd-search.xml", {'base_url': cherrypy.url('/')})
    
    def startup(self):
        form = PassphraseSubmitForm()
        return render("startup.html", {'form': form})

    def initialize(self, **kwargs):
        form = PassphraseSubmitForm(request_params())
        if form.validate():
            crypto_util.configure_crypto_state(form.passphrase.data)
            raise cherrypy.HTTPRedirect("/")
        else:
            return render("startup.html", {'form': form})
    
    def login(self, redirect=None):     
        form = LoginForm(redirect=redirect)
        return render("login.html", {'auth_provider': config['auth.provider'], 'form': form})
    
    def process_login(self, **kwargs):
        form = LoginForm(request_params())

        # TODO: Refactor to combine with the ensconce.server:checkpassword method.  Lots of duplicate
        # logic here.  AT MINIMUM MAKE SURE THAT ANY CHANGES HERE ARE REFLECTED THERE
        
        # This is a "flow-control" exception. ... You'll see. :)        
        class _LoginFailed(Exception):
            pass
        
        try:
            if not form.validate():
                raise _LoginFailed()
        
            username = form.username.data
            password = form.password.data
            
            for auth_provider in get_configured_providers():
                try:
                    auth_provider.authenticate(username, password)
                except exc.InsufficientPrivileges:
                    form.username.errors.append(ValidationError("Insufficient privileges to log in."))
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
                form.password.errors.append(ValidationError("Invalid username/password."))
                raise _LoginFailed()
            
        except _LoginFailed:
            auditlog.log(auditlog.CODE_AUTH_FAILED, comment=username)
            return render("login.html", {'auth_provider': config['auth.provider'], 'form': form})
        else:
            
            # Resolve the user using the *current value* for auth_provider (as that is the one that passed the auth.
            user = auth_provider.resolve_user(username)
            
            log.debug("Setting up cherrypy session with username={0}, user_id={1}".format(username, user.id))    
            cherrypy.session['username'] = username # @UndefinedVariable
            cherrypy.session['user_id'] = user.id # @UndefinedVariable
            
            auditlog.log(auditlog.CODE_AUTH_LOGIN)
            
            if form.redirect.data:
                raise cherrypy.HTTPRedirect(form.redirect.data)
            else:
                raise cherrypy.HTTPRedirect("/")

    def logout(self):
        auditlog.log(auditlog.CODE_AUTH_LOGOUT)
        cherrypy.session.clear() # @UndefinedVariable
        raise cherrypy.HTTPRedirect("/")

    @acl.require_access(acl.AUDIT)
    def auditlog(self, **kwargs):
        form = AuditlogForm(request_params())
        
        page_size = 50
        page = form.page.data
        offset = page_size * (page - 1)
        limit = page_size
        
        log.debug("Page = {0}, offset={1}, limit={2}".format(page, offset, limit))
        results = auditlog.search(start=form.start.data,
                                  end=form.end.data,
                                  code=form.code.data,
                                  operator_username=form.operator.data,
                                  offset=offset,
                                  limit=limit)
        
        if results.count < offset:
            form.page.data = 1
            form.page.raw_data = ['1'] # Apparently need this too!
        
        total_pages = int(math.ceil( (1.0 * results.count) / page_size))  
        return render('auditlog.html', {'entries': results.entries, 'form': form, 'total_pages': total_pages})
    
    @acl.require_access([acl.GROUP_R, acl.RESOURCE_R, acl.PASS_R])
    def search(self, searchstr):
        r_matches = g_matches = p_matches = None
        if searchstr:
            (r_matches, g_matches, p_matches) = search.search(searchstr, include_encrypted=True)
            if len(r_matches) + len(g_matches) + len(p_matches) == 1:
                # There was only one result, so just send them to the resulting page.
                notify("Showing you the one result that matched your query.")
                if r_matches:
                    raise cherrypy.HTTPRedirect("/resource/view/{0}".format(r_matches[0].id))
                elif g_matches:
                    raise cherrypy.HTTPRedirect("/group/view/{0}".format(g_matches[0].id))
                elif p_matches:
                    # We could also redirect them to the password view/history page if that is more helpful?
                    raise cherrypy.HTTPRedirect("/resource/view/{0}".format(p_matches[0].resource_id)) 
            
            auditlog.log(auditlog.CODE_SEARCH, comment=searchstr)
        return render('search.html', {'resource_matches': r_matches,
                                      'group_matches': g_matches,
                                      'password_matches': p_matches,
                                      'searchstr': searchstr })


