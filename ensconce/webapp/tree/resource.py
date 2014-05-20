from __future__ import absolute_import
import math

import cherrypy

from wtforms import (Form, TextAreaField, TextField, IntegerField, SelectField, HiddenField, 
                     SelectMultipleField, validators, widgets, ValidationError)

from ensconce import acl
from ensconce.cya import auditlog
from ensconce.crypto import engine
from ensconce.model import Resource
from ensconce.dao import groups, resources, passwords
from ensconce.autolog import log

from ensconce.webapp.tree import expose_all
from ensconce.webapp.util import render, notify_entity_activity, request_params


class MultiCheckboxField(SelectMultipleField):
    """
    A multiple-select, except displays a list of checkboxes.

    Iterating the field will produce subfields, allowing custom rendering of
    the enclosed checkbox fields.
    """
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()

def check_duplicate_name(form, field):    
    name = field.data
    for group_id in form.group_ids.data:
        group = groups.get(group_id)
        q = group.resources.filter_by(name=name)
        if hasattr(form, 'resource_id'):
            q = q.filter(Resource.id != form.resource_id.data) # @UndefinedVariable
        existing = q.all()
        if existing:
            raise ValidationError("Resource \"{0}\" already exists in group \"{1}\".".format(name, group.name))
     
class ResourceAddForm(Form):
    name = TextField('Name', validators=[validators.Length(max=255), validators.Required(), check_duplicate_name])
    addr = TextField('IP Address', validators=[validators.Length(max=255)]) # We may wish to add validators.IPAddress(), but that will also make it required currently.
    description = TextField('Description', validators=[validators.Length(max=255)])
    notes_decrypted = TextAreaField('Notes', validators=[validators.Length(max=6000)])
    # TODO: See "BetterTagListField" http://wtforms.simplecodes.com/docs/1.0.3/fields.html
    tags = TextField('Tags', validators=[validators.Length(max=1024),
                                         validators.Regexp(r'^[ \w\-:]*$',
                                                           message="Tags may only contain alpha-numeric, dash, colon, and underscore characters and are separated by spaces."),])
    group_ids = SelectMultipleField('Groups', validators=[validators.Required()], coerce=int)
    

class ResourceEditForm(ResourceAddForm):
    resource_id = HiddenField(validators=[validators.Required()])
    
@expose_all()
class Root(object):
    
    @acl.require_access(acl.RESOURCE_R)
    def view(self, resource_id):
        try:
            resource_id = int(resource_id)
        except ValueError:
            resource = resources.get_by_name(resource_id, assert_single=True)
        else:
            resource = resources.get(resource_id)
        
        auditlog.log(auditlog.CODE_CONTENT_VIEW, target=resource)
        return render('resource/view.html', {'resource': resource})
        
    @acl.require_access([acl.GROUP_R, acl.RESOURCE_R])    
    def list(self, **kwargs):
        class PagerForm(Form):
            page = SelectField('Page', default=1, coerce=int)
    
        form = PagerForm(request_params())
        page_size = 50
        page = form.page.data
        offset = page_size * (page - 1)
        limit = page_size
        results = resources.search(limit=limit, offset=offset)
        total_pages = int(math.ceil( (1.0 * results.count) / page_size))
        
        form.page.choices = [(i, i) for i in range(1, total_pages+1)]
        
        return render('resource/list.html', {'resources': results.entries,
                                             'form': form,
                                             'page': page,
                                             'total_pages': total_pages})

    @acl.require_access([acl.GROUP_R, acl.RESOURCE_R])
    def add(self, group_id=None):
        group_ids = []
        if group_id:
            group_ids = [group_id]
            
        form = ResourceAddForm(group_ids=group_ids)
        form.group_ids.choices = [(g.id, g.label) for g in groups.list()]
        return render('resource/add.html', {'form': form })

    @acl.require_access([acl.GROUP_R, acl.RESOURCE_R, acl.RESOURCE_W])
    def process_add(self, **kwargs):
        form = ResourceAddForm(request_params())
        form.group_ids.choices = [(g.id, g.label) for g in groups.list()]
        if form.validate():
            resource = resources.create(name=form.name.data,
                                        group_ids=form.group_ids.data,
                                        addr=form.addr.data,
                                        description=form.description.data, 
                                        notes=form.notes_decrypted.data,
                                        tags=form.tags.data) # XXX: process
            auditlog.log(auditlog.CODE_CONTENT_ADD, target=resource)
            notify_entity_activity(resource, 'created')
            raise cherrypy.HTTPRedirect('/resource/view/{0}'.format(resource.id))
        else:
            return render('resource/add.html', {'form': form })
    
    @acl.require_access([acl.GROUP_R, acl.RESOURCE_R, acl.RESOURCE_W])
    def edit(self, resource_id):
        resource = resources.get(resource_id)
        log.debug("Resource matched: {0!r}".format(resource))
        form = ResourceEditForm(request_params(), obj=resource, resource_id=resource_id, group_ids=[g.id for g in resource.groups])
        form.group_ids.choices = [(g.id, g.label) for g in groups.list()]
        return render('resource/edit.html', {'form': form})
    
    @acl.require_access([acl.GROUP_R, acl.RESOURCE_R, acl.RESOURCE_W])
    def process_edit(self, **kwargs):
        form = ResourceEditForm(request_params())
        form.group_ids.choices = [(g.id, g.label) for g in groups.list()]
        if form.validate():
            (resource, modified) = resources.modify(form.resource_id.data,
                                                    name=form.name.data,
                                                    addr=form.addr.data,
                                                    group_ids=form.group_ids.data,
                                                    notes=form.notes_decrypted.data,
                                                    description=form.description.data,
                                                    tags=form.tags.data) # XXX: process
            auditlog.log(auditlog.CODE_CONTENT_MOD, target=resource, attributes_modified=modified)
            notify_entity_activity(resource, 'updated')
            raise cherrypy.HTTPRedirect('/resource/view/{0}'.format(resource.id))
        else:
            log.warning("Form validation failed.")
            log.warning(form.errors)
            return render('resource/edit.html', {'form': form})
        
    @acl.require_access([acl.RESOURCE_R, acl.RESOURCE_W]) 
    def delete(self, resource_id, redirect_to=None):
        resource = resources.get(resource_id)
        if cherrypy.request.method == 'POST':
            
            # First remove any passwords for this resource.
            for pw in resource.passwords:
                del_pw = passwords.delete(pw.id)
                auditlog.log(auditlog.CODE_CONTENT_DEL, target=del_pw)
        
            # Then remove the actual resource
            resource = resources.delete(resource_id)
            auditlog.log(auditlog.CODE_CONTENT_DEL, target=resource)
            notify_entity_activity(resource, 'deleted')
            if redirect_to:
                raise cherrypy.HTTPRedirect(redirect_to)
            else:
                raise cherrypy.HTTPRedirect('/resource/list')
        else:
            return render('resource/delete.html', {'resource': resource,
                                                   'redirect_to': redirect_to})