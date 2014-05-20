from __future__ import absolute_import

import cherrypy
from wtforms import Form, IntegerField, TextField, TextAreaField, validators, widgets, ValidationError

from ensconce import acl
from ensconce.util import pwtools
from ensconce.model import Password
from ensconce.dao import passwords, resources
from ensconce.cya import auditlog
from ensconce.webapp.tree import expose_all
from ensconce.webapp.util import render, notify_entity_activity, request_params
from ensconce.autolog import log

# This is not actually used anymore, since it appears
# that this assumption of uniqueness within a resource was wrong.
def check_duplicate_username(form, field):    
    username = field.data
    existing = resource = None
    if hasattr(form, 'resource_id'):
        # It's being added
        resource = resources.get(form.resource_id.data)
        existing = resource.passwords.filter_by(username=username).first()
    elif hasattr(form, 'password_id'):
        # Lookup from pw_id
        pw = passwords.get(form.password_id.data)
        resource = pw.resource
        q = resource.passwords.filter_by(username=username)
        q = q.filter(Password.id != pw.id) # @UndefinedVariable
        existing = q.first()
    else:
        raise Exception("Unexpected condition.")
    
    if existing:
        raise ValidationError("Username \"{0}\" already exists for this resource \"{1}\".".format(username, resource.name))

class CommonPasswordForm(Form):
    username = TextField('Username', validators=[validators.Length(max=255), validators.Required()])
    description = TextField('Description', validators=[validators.Length(max=255)])
    # TODO: See "BetterTagListField" http://wtforms.simplecodes.com/docs/1.0.3/fields.html
    tags = TextField('Tags', validators=[validators.Length(max=1024),
                                         validators.Regexp(r'^[ \w\-:]*$',
                                                           message="Tags may only contain alpha-numeric, dash, colon, and underscore characters and are separated by spaces."),])
    password_decrypted = TextAreaField('Password', validators=[validators.Length(max=8192), validators.Required()])
    
class PasswordAddForm(CommonPasswordForm):
    resource_id = IntegerField(validators=[validators.Required()], widget=widgets.HiddenInput())

class PasswordEditForm(CommonPasswordForm):
    password_id = IntegerField(validators=[validators.Required()], widget=widgets.HiddenInput())

@expose_all()
class Root(object):
    
    def generate(self, digits, lower, upper, nonalpha, length, nonambig, _):
        """
        (AJAX) Generate a password and return the text of the new password.
        
        (jquery will pass an additional _ arg for no-caching purposes.)
        """
        return pwtools.generate_password(length=int(length),
                                         ascii_lower=int(lower),
                                         ascii_upper=int(upper),
                                         punctuation=int(nonalpha),
                                         digits=int(digits),
                                         strip_ambiguous=int(nonambig))
    
    @acl.require_access(acl.PASS_R)
    def reveal(self, password_id, _=None):
        """
        (AJAX) Returns the specified password.  (This is a separate action for the purposes of auditing.)
        
        (jquery will pass an additional _ arg for no-caching purposes.)
        """
        pw = passwords.get(password_id)
        if not pw:
            raise ValueError("Invalid password specified: {0}".format(password_id))
        
        auditlog.log(auditlog.CODE_CONTENT_VIEW, target=pw)
        return pw.password_decrypted
    
    @acl.require_access([acl.PASS_R])
    def view(self, password_id):
        pw = passwords.get(password_id)
        auditlog.log(auditlog.CODE_CONTENT_VIEW, target=pw)
        return render('password/view.html', {'password': pw})
    
    @acl.require_access([acl.PASS_R, acl.PASS_W])
    def add(self, resource_id):
        form = PasswordAddForm(request_params())
        return render('password/add.html', {'form': form})
    
    @acl.require_access([acl.PASS_R, acl.PASS_W])
    def process_add(self, **kwargs):
        form = PasswordAddForm(request_params())
        if form.validate():
            pw = passwords.create(username=form.username.data,
                                  resource_id=form.resource_id.data,
                                  password=form.password_decrypted.data,
                                  description=form.description.data,
                                  tags=form.tags.data)
            auditlog.log(auditlog.CODE_CONTENT_ADD, target=pw)
            notify_entity_activity(pw, 'created')
            raise cherrypy.HTTPRedirect('/resource/view/%d' % pw.resource_id)
        else:
            return render('password/add.html', {'form': form})

    @acl.require_access([acl.PASS_R, acl.PASS_W])
    def edit(self, password_id):
        pw = passwords.get(password_id)
        form = PasswordEditForm(request_params(), obj=pw, password_id=pw.id)
        return render('password/edit.html', {'form': form})
    
    @acl.require_access([acl.PASS_R, acl.PASS_W])
    def process_edit(self, **kwargs):
        form = PasswordEditForm(request_params())
        if form.validate():
            (pw, modified) = passwords.modify(form.password_id.data, 
                                              username=form.username.data, 
                                              password=form.password_decrypted.data, 
                                              description=form.description.data,
                                              tags=form.tags.data)
    
            auditlog.log(auditlog.CODE_CONTENT_MOD, target=pw,
                         attributes_modified=modified)
            notify_entity_activity(pw, 'updated')
            raise cherrypy.HTTPRedirect('/resource/view/{0}'.format(pw.resource_id))
        else:
            log.warning("Form failed validation: {0}".format(form.errors))
            return render('password/edit.html', {'form': form})
        
    @acl.require_access([acl.PASS_R, acl.PASS_W])
    def delete(self, password_id):
        pw = passwords.delete(password_id)
        auditlog.log(auditlog.CODE_CONTENT_DEL, target=pw)
        notify_entity_activity(pw, 'deleted')
        raise cherrypy.HTTPRedirect('/resource/view/%d' % int(pw.resource_id))
    