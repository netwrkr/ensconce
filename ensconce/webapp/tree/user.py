from __future__ import absolute_import

import cherrypy
from wtforms import Form, IntegerField, TextField, SelectField, validators, widgets, PasswordField, ValidationError

 
from ensconce import acl
from ensconce.dao import operators, access
from ensconce.cya import auditlog

from ensconce.webapp.tree import expose_all
from ensconce.webapp.util import render, notify_entity_activity, request_params
from ensconce.autolog import log

def check_duplicate_name(form, field):
    name = field.data
    existing = operators.get_by_username(name, assert_exists=False)
    if existing:
        if not hasattr(form, 'operator_id') or (hasattr(form, 'operator_id') and \
                                             existing.id != form.operator_id.data):
            raise ValidationError("Operator \"{0}\" already exists.".format(name))
        
class OperatorAddForm(Form):
    username = TextField('Username', validators=[validators.Length(max=255),
                                                 validators.Required(),
                                                 validators.Regexp(r'^[\w\-\._]*$',
                                                                   message="Only alpha-numeric, dash, and underscore characters allowed."),
                                                 check_duplicate_name])
    password = PasswordField('Password', validators=[validators.Length(max=2048)])
    access_id = SelectField('Access Level', validators=[validators.Required()], coerce=int)
    
class OperatorEditForm(OperatorAddForm):
    operator_id = IntegerField(validators=[validators.Required()], widget=widgets.HiddenInput())


@expose_all()
class Root(object):
        
    @acl.require_access(acl.USER_R)
    def view(self, operator_id):
        operator = operators.get(operator_id)
        auditlog.log(auditlog.CODE_CONTENT_VIEW, target=operator)
        return render('user/view.html', {'operator': operator })
            
    @acl.require_access(acl.USER_R)
    def list(self):
        return render('user/list.html', {'users': operators.list()})
    
    @acl.require_access([acl.USER_R, acl.USER_W])
    def delete(self, operator_id):
        operator = operators.delete(operator_id)
        auditlog.log(auditlog.CODE_CONTENT_DEL, target=operator)
        notify_entity_activity(operator, 'deleted')
        raise cherrypy.HTTPRedirect('/user/list')
    
    @acl.require_access([acl.ACCESS_R, acl.USER_W])
    def add(self):
        form = OperatorAddForm()
        form.access_id.choices = [(l.id, l.description) for l in access.list()]
        return render('user/add.html', {'form': form })
    
    @acl.require_access([acl.USER_R, acl.USER_W])
    def process_add(self, **kwargs):
        form = OperatorAddForm(request_params())
        form.access_id.choices = [(l.id, l.description) for l in access.list()]
        if form.validate():
            operator = operators.create(username=form.username.data,
                                        password=form.password.data,
                                        access_id=form.access_id.data)
            auditlog.log(auditlog.CODE_CONTENT_ADD, target=operator)
            notify_entity_activity(operator, 'created')
            raise cherrypy.HTTPRedirect('/user/list')
        else:
            return render('user/add.html', {'form': form })

    @acl.require_access([acl.ACCESS_R, acl.USER_R, acl.USER_W])
    def edit(self, operator_id):
        operator = operators.get(operator_id)
        form = OperatorEditForm(request_params(), obj=operator, operator_id=operator_id)
        form.access_id.choices = [(l.id, l.description) for l in access.list()]
        return render('user/edit.html', {'form': form, 'externally_managed': operator.externally_managed})
    
    @acl.require_access([acl.USER_R, acl.USER_W])
    def process_edit(self, **kwargs):
        log.debug("params = %r" % request_params())
        form = OperatorEditForm(request_params())
        form.access_id.choices = [(l.id, l.description) for l in access.list()]
        if form.validate():
            params = dict(operator_id=form.operator_id.data,
                          username=form.username.data,
                          access_id=form.access_id.data)
            
            # If password is blank, let's just not change it.
            if form.password.data:
                params['password'] = form.password.data
                
            (operator, modified) = operators.modify(**params)
            auditlog.log(auditlog.CODE_CONTENT_MOD, target=operator, attributes_modified=modified)
            notify_entity_activity(operator, 'updated')
            raise cherrypy.HTTPRedirect('/user/list')
        else:
            return render('user/edit.html', {'form': form, 'externally_managed': operator.externally_managed})


    