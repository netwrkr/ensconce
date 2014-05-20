from __future__ import absolute_import

import cherrypy
from wtforms import Form, TextField, SelectMultipleField, validators

from ensconce import acl
from ensconce.cya import auditlog
from ensconce.dao import access
from ensconce.webapp.tree import expose_all
from ensconce.webapp.util import render, request_params, notify_entity_activity

class AccessAddForm(Form):
    description = TextField('Description', validators=[validators.Length(max=255),
                                                       validators.Regexp(r'^[\w\-\._ ]*$',
                                                                         message="Only alpha-numeric, space, dash, and underscore characters allowed.")])
    levels = SelectMultipleField('Access Levels', choices=acl.ACCESS_LEVEL_LABELS, validators=[validators.Required()], coerce=int)


@expose_all()
class Root(object):
    
    @acl.require_access(acl.ACCESS_R)
    def list(self):
        return render('access/list.html', {'access': access.list()})
        
    @acl.require_access(acl.ACCESS_R)
    def view(self, access_id):
        level = access.get(access_id)
        auditlog.log(auditlog.CODE_CONTENT_VIEW, target=level)
        level_includes = lambda have, want: (have & want) != 0 # This is needed because jinja is whining about the '&' in the conditional
        return render('access/view.html', {'level': level,
                                           'level_includes': level_includes,
                                           'acl_labels': acl.ACCESS_LEVEL_LABELS})
        
    @acl.require_access([acl.ACCESS_W, acl.ACCESS_R])
    def add(self):
        form = AccessAddForm()
        return render('access/add.html', {'form': form})
    
    @acl.require_access([acl.ACCESS_W, acl.ACCESS_R])
    def process_add(self, **kwargs):
        form = AccessAddForm(request_params())
        if form.validate():
            level_mask = 0
            for i in form.levels.data:
                level_mask |= int(i)
    
            level = access.create(level_mask, form.description.data)
            auditlog.log(auditlog.CODE_CONTENT_ADD, target=level)
            notify_entity_activity(level, 'created')
            raise cherrypy.HTTPRedirect('/access/list')
        else:
            return render('access/add.html', {'form': form})
    
    @acl.require_access([acl.ACCESS_W, acl.ACCESS_R])
    def delete(self, access_id):
        level = access.delete(access_id)
        auditlog.log(auditlog.CODE_CONTENT_DEL, target=level)
        notify_entity_activity(level, 'deleted')
        raise cherrypy.HTTPRedirect('/access/list')