from __future__ import absolute_import
import os.path
import re
import tempfile
from io import BytesIO

import cherrypy
from cherrypy.lib.static import serve_fileobj

from wtforms import Form, TextField, IntegerField, SelectField, PasswordField, validators, widgets, ValidationError, SelectMultipleField

from ensconce import acl, model
from ensconce.dao import groups, resources, passwords
from ensconce.cya import auditlog
from ensconce.export import GpgAes256, GpgYamlExporter, KeepassExporter
from ensconce.webapp.tree import expose_all
from ensconce.webapp.util import render, notify_entity_activity, request_params, operator_info
from ensconce.autolog import log
from ensconce.config import config

def check_duplicate_name(form, field):
    name = field.data
    existing = groups.get_by_name(name, assert_exists=False)
    if existing:
        if not hasattr(form, 'group_id') or (hasattr(form, 'group_id') and \
                                             existing.id != form.group_id.data):
            raise ValidationError("Group \"{0}\" already exists.".format(name))

def check_match_passphrase(form, field):
    if field.data != form.passphrase.data:
        raise ValidationError("Passphrases do not match.")
    
class GroupAddForm(Form):
    name = TextField('Name', [validators.Length(max=255), validators.Required(), check_duplicate_name])

class GroupEditForm(GroupAddForm):
    group_id = IntegerField('group_id', validators=[validators.Required()], widget=widgets.HiddenInput())

class ExportForm(Form):
    group_id = SelectField('Group', validators=[validators.Required()], coerce=int)
    passphrase = PasswordField('Passphrase', [validators.Length(min=12), validators.Required()])
    passphrase_repeat = PasswordField('Repeat Passphrase', [validators.Required(), check_match_passphrase])
    format = SelectField('Format', choices=[], validators=[validators.Required()])

def check_not_same_as_from_group(form, field):
    if field.data == form.from_group_id.data:
        raise ValidationError("Cannot merge a group into itself.")
        
class MergeForm(Form):
    from_group_id = SelectField('Merge From', validators=[validators.Required()], coerce=int)
    to_group_id = SelectField('Merge Into', validators=[validators.Required(), check_not_same_as_from_group], coerce=int)

@expose_all()
class Root(object):
    
    @acl.require_access([acl.GROUP_R, acl.RESOURCE_R, acl.PASS_R])
    def export(self, group_id=None, **kwargs):
        form = ExportForm(request_params(), group_id=group_id)
        form.group_id.choices = [(g.id, g.name) for g in groups.list()]
        
        exporter_choices = [('yaml', 'YAML (GPG/PGP-encrypted)')]
        if config['export.keepass.enabled']:
            if not os.path.exists(config['export.keepass.exe_path']):
                log.error("KeePass export enabled, but specified converter script does not exist: {0}".format(config.get('export.keepass.exe_path')))
            else:
                exporter_choices.append(('kdb', 'KeePass 1.x'))
        form.format.choices = exporter_choices
        
        if cherrypy.request.method == 'POST':
            if form.validate():
                group = groups.get(form.group_id.data)
                
                if form.format.data == 'yaml':
                    exporter = GpgYamlExporter(use_tags=False,
                                               passphrase=form.passphrase.data,
                                               resource_filters=[model.GroupResource.group_id==group.id]) # @UndefinedVariable
                    encrypted_stream = BytesIO()
                    exporter.export(stream=encrypted_stream)
                    encrypted_stream.seek(0) # Just to ensure it's rewound
                    
                    return serve_fileobj(encrypted_stream, content_type='application/pgp-encrypted', disposition='attachment',
                                         name='group-{0}-export.pgp'.format(re.sub('[^\w\-\.]', '_', group.name)))
                    
                elif form.format.data == 'kdb':
                    exporter = KeepassExporter(passphrase=form.passphrase.data,
                                               resource_filters=[model.GroupResource.group_id==group.id]) # @UndefinedVariable
                    encrypted_stream = BytesIO()
                    exporter.export(stream=encrypted_stream)
                    encrypted_stream.seek(0) # Just to ensure it's rewound
                    
                    return serve_fileobj(encrypted_stream, content_type='application/x-keepass-database', disposition='attachment',
                                         name='group-{0}-export.kdb'.format(re.sub('[^\w\-\.]', '_', group.name)))
                        
                else:
                    # I don't think we can get here in normal business.
                    raise RuntimeError("Unhandled format specified: {0}".format(form.format.data))
                    
            else: # does not validate
                return render("group/export.html", {'form': form})
        else: # request method is GET
            return render("group/export.html", {'form': form})
    
    @acl.require_access([acl.GROUP_R, acl.GROUP_W, acl.RESOURCE_W])
    def merge(self, group_id=None):
        form = MergeForm(from_group_id=group_id)
        group_tuples = [(g.id, g.name) for g in groups.list()]
        form.from_group_id.choices = [(0, '[From Group]')] + group_tuples
        form.to_group_id.choices = [(0, '[To Group]')] + group_tuples
        return render("group/merge.html", {'form': form})
    
    @acl.require_access([acl.GROUP_W, acl.RESOURCE_W])
    def process_merge(self, **kwargs):
        form = MergeForm(request_params())
        group_tuples = [(g.id, g.name) for g in groups.list()]
        form.from_group_id.choices = [(0, '[From Group]')] + group_tuples
        form.to_group_id.choices = [(0, '[To Group]')] + group_tuples
        if form.validate():
            log.info("Passed validation, somehow.")
            (moved_resources, from_group, to_group) = groups.merge(form.from_group_id.data, form.to_group_id.data)
            for r in moved_resources:
                auditlog.log(auditlog.CODE_CONTENT_MOD, target=r, attributes_modified=['group_id'])
            auditlog.log(auditlog.CODE_CONTENT_DEL, target=from_group)
            raise cherrypy.HTTPRedirect('/group/view/{0}'.format(to_group.id))
        else:
            return render("group/merge.html", {'form': form})


    @acl.require_access(acl.GROUP_R)
    def view(self, group_id):
        try:
            group_id = int(group_id)
        except ValueError:
            group = groups.get_by_name(group_id)
        else:
            group = groups.get(group_id)
            
        auditlog.log(auditlog.CODE_CONTENT_VIEW, target=group)
        return render("group/view.html", {'group': group})
    
    @acl.require_access(acl.GROUP_R)
    def list(self):
        return render('group/list.html', {'groups': groups.list()})
        
    @acl.require_access([acl.GROUP_R, acl.GROUP_W])
    def add(self):
        return render("group/add.html", {'form': GroupAddForm()})

    @acl.require_access([acl.GROUP_R, acl.GROUP_W])
    def process_add(self, **kwargs): # We don't specify the args explicitly since we are using wtforms here.
        form = GroupAddForm(request_params())
        if form.validate():
            group = groups.create(name=form.name.data)
            auditlog.log(auditlog.CODE_CONTENT_ADD, target=group)
            notify_entity_activity(group, 'created')
            raise cherrypy.HTTPRedirect('/group/list')
        else:
            return render("group/add.html", {'form': form})
        
    @acl.require_access([acl.GROUP_R, acl.GROUP_W])
    def edit(self, group_id):
        group = groups.get(group_id)
        form = GroupEditForm(request_params(), group, group_id=group.id)
        return render('group/edit.html', {'form': form})
    
    @acl.require_access([acl.GROUP_R, acl.GROUP_W])
    def process_edit(self, **kwargs):
        """
        Updates a group (changes name).
        """
        form = GroupEditForm(request_params())
        if form.validate():
            (group, modified) = groups.modify(form.group_id.data, name=form.name.data)
        
            auditlog.log(auditlog.CODE_CONTENT_MOD, target=group, attributes_modified=modified)
            notify_entity_activity(group, 'updated')
            raise cherrypy.HTTPRedirect('/group/list')
        else:
            return render('group/edit.html', {'form': form})
    
    @acl.require_access([acl.GROUP_R, acl.GROUP_W, acl.RESOURCE_R, acl.RESOURCE_W, acl.PASS_R, acl.PASS_W])
    def delete(self, group_id):
        """
        Deletes a group.
        """
        group = groups.get(group_id)
        
        all_resources = group.resources.all()
        
        # This is very lazy (could be done in SQL), but simple/easy-to-debug.
        resources_only_in_this_group = []
        resources_in_other_groups_too = [] 
        for r in all_resources:
            if r.groups.all() == [group]:
                resources_only_in_this_group.append(r)
            else:
                resources_in_other_groups_too.append(r)
        
        if cherrypy.request.method == 'POST':
       
            # First remove any resources that are only owned by this group. 
            for r in resources_only_in_this_group:
                # Remove any passwords in this resource
                for pw in r.passwords:
                    del_pw = passwords.delete(pw.id)
                    auditlog.log(auditlog.CODE_CONTENT_DEL, target=del_pw)
                del_r = resources.delete(r.id)
                auditlog.log(auditlog.CODE_CONTENT_DEL, target=del_r)
            
            # Next we manually remove the group from any other resources that were associated
            # with this group.
            for r in resources_in_other_groups_too:
                group_ids = set([g.id for g in r.groups.all()])
                group_ids.remove(group.id)
                (mod_r, modified) = resources.modify(r.id, group_ids=group_ids)
                if modified:
                    auditlog.log(auditlog.CODE_CONTENT_MOD, target=mod_r, attributes_modified=modified)
            
            # And finally we can delete the group itself.
            group = groups.delete(group.id)
            auditlog.log(auditlog.CODE_CONTENT_DEL, target=group)
            
            notify_entity_activity(group, 'deleted')
            raise cherrypy.HTTPRedirect('/group/list')
        else:
            return render('group/delete.html', {'group_id': group_id,
                                                'del_resources': resources_only_in_this_group,
                                                'mod_resources': resources_in_other_groups_too})