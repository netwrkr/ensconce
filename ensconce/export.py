"""
Classes to support [encrypted] database export and import.

Classes in this module do not write out any files to the filesystem; it is the
responsibility of the calling code to handle the persistence of any file streams
(and make sure it's done securely, etc.).
"""
import os
import abc
from cStringIO import StringIO
import tempfile

import pexpect
import gnupg
from sqlalchemy import and_
import yaml

from ensconce import model, exc
from ensconce.model import meta
from ensconce.config import config
from ensconce.autolog import log
from ensconce.dao import passwords, resources, groups
from sqlalchemy.orm.exc import MultipleResultsFound

class GpgAes256(gnupg.GPG):
    """
    By default we'd like to use AES256 instead of CAST5, since this will include
    MDC integrity validation.
    """
    def __init__(self, *args, **kwargs):
        if kwargs.get('options') is not None:
            kwargs['options'].append('--cipher-algo=AES256')
        else:
            kwargs['options'] = ['--cipher-algo=AES256']
        super(GpgAes256, self).__init__(*args, **kwargs)
    
class Exporter(object):
    __metaclass__ = abc.ABCMeta
    
    include_key_metadata = False
    resource_filters = None
    password_filters = None
    
    def __init__(self, resource_filters=None, password_filters=None, include_key_metadata=False):
        if resource_filters is None:
            resource_filters = []
        if password_filters is None:
            password_filters = []
        self.resource_filters = resource_filters
        self.password_filters = password_filters
        self.include_key_metadata = include_key_metadata
    
    @abc.abstractmethod
    def export(self, stream):
        """
        Export database contents to specified stream (file-like object).
        """
        pass
    
    # This is expected to expand as we probably want to be able to pass our exporters
    # some standard options (about which entities to include, etc.)
    
class DictExporter(Exporter):
    """
    Common functionality for exporting the model as a python dict.
    """
    def build_structure(self):
        """
        Builds a python dictionary of the entire database structure we want to export.
        """
        session = meta.Session()
        
        content = {}
        
        # TODO key metadata?
        if self.include_key_metadata:
            content['key_metadata'] = [kmd.to_dict(encode=False) for kmd in session.query(model.KeyMetadata).all()]
            
        content['resources'] = []
        
        rsrc_t = model.resources_table
        pass_t = model.passwords_table
        grp_t = model.groups_table
        
        q = session.query(model.Resource).order_by(rsrc_t.c.name)
        if self.resource_filters:
            q = q.join(model.GroupResource)
            q = q.filter(and_(*self.resource_filters))
            
        q = q.order_by(rsrc_t.c.name)
        for resource in q.all():
            rdict = resource.to_dict(decrypt=True)
            pw_q = resource.passwords
            if self.password_filters:
                pw_q = pw_q.filter(and_(*self.password_filters))
            pw_q = pw_q.order_by(pass_t.c.username)
            rdict['passwords'] = [pw.to_dict(decrypt=True) for pw in pw_q.all()]
            rdict['groups'] = [g.name for g in resource.groups.order_by(grp_t.c.name).all()]
            content['resources'].append(rdict)
            
        return content
    
class YamlExporter(DictExporter):
    
    def __init__(self, use_tags=True, resource_filters=None, password_filters=None,
                 include_key_metadata=False):
        super(YamlExporter, self).__init__(resource_filters=resource_filters,
                                           password_filters=password_filters,
                                           include_key_metadata=include_key_metadata)
        
        self.use_tags = use_tags
        
    def export(self, stream):
        """
        """
        if not hasattr(stream, 'write'):
            raise TypeError("stream must be a file-like object.")
        
        if not self.use_tags:
            DumperClass = yaml.SafeDumper
        else:
            DumperClass = yaml.Dumper
            
        yaml.dump(self.build_structure(), stream=stream, Dumper=DumperClass)
    

class GpgYamlExporter(YamlExporter):
    
    def __init__(self, passphrase, use_tags=True, resource_filters=None, 
                 password_filters=None, include_key_metadata=False):
        super(GpgYamlExporter, self).__init__(use_tags=use_tags,
                                              resource_filters=resource_filters,
                                              password_filters=password_filters,
                                              include_key_metadata=include_key_metadata)
        self.passphrase = passphrase
    
    def export(self, stream):
        """
        """
        # Create a new stream to pass in to the parent
        yaml_stream = StringIO()
        super(GpgYamlExporter, self).export(yaml_stream)
        
        # reset our stream
        yaml_stream.seek(0)
        
        gpg = GpgAes256()
        encrypted = gpg.encrypt_file(yaml_stream, recipients="user@example.com",
                                     passphrase=self.passphrase, symmetric=True)
        
        stream.write(str(encrypted))
        stream.seek(0)
      
class KeepassExporter(GpgYamlExporter):
    
    def __init__(self, passphrase, resource_filters=None, password_filters=None,
                 include_key_metadata=False):
        super(KeepassExporter, self).__init__(use_tags=False,
                                              passphrase=passphrase,
                                              resource_filters=resource_filters,
                                              password_filters=password_filters,
                                              include_key_metadata=include_key_metadata)
        
    def export(self, stream):
        """
        """
        gpg_filename = None
        kdb_filename = None
        
        try:
            with tempfile.NamedTemporaryFile(suffix='.yaml.gpg', prefix='export', delete=False) as gpg_fp:
                super(KeepassExporter, self).export(gpg_fp)
                gpg_filename = gpg_fp.name
                
            kdb_fp = tempfile.NamedTemporaryFile(suffix='.kdb', prefix='export', delete=False) # We have to manually delete this one
            kdb_filename = kdb_fp.name
            kdb_fp.close()
            
            cmd_exe = config['export.keepass.exe_path']
            args = ['-i', gpg_filename, '-o', kdb_filename]
            log.info("Executing command: {0} {1}".format(cmd_exe, ' '.join(args)))
            child = pexpect.spawn(cmd_exe, args)
            child.expect('ssphrase')
            child.sendline(self.passphrase)                
            child.expect(pexpect.EOF)
            log.debug(child.before)
            
            with open(kdb_filename) as read_fp:
                # Read contents of file into our own stream
                kdb_bytes = read_fp.read()
                stream.write(kdb_bytes)
                log.debug("Read {0} bytes from kdb file stream".format(len(kdb_bytes)))
                stream.seek(0)
                
        finally:
            if gpg_filename:
                os.remove(gpg_filename)
            if kdb_filename:
                os.remove(kdb_filename)
                
                
# ----------------------------------------------------------------------------
# IMPORTER CLASSES
# ----------------------------------------------------------------------------
                
class Importer(object):
    __metaclass__ = abc.ABCMeta
    
    def __init__(self, force=False):
        self.force = force
        
    @abc.abstractmethod
    def execute(self, stream):
        """
        Import database contents from specified stream (file-like object).
        """
        pass
    
    
class DictImporter(Importer):
    """
    Common functionality for importing the model from a python dict.
    """
    def from_structure(self, structure):
        """
        Populates the SQLAlchemy model from a python dictionary of the database structure.
        """
        session = meta.Session()
        
        try:
            for resource_s in structure['resources']:
                log.debug("Importing: {0!r}".format(resource_s))
                
                # First build up a list of group_ids for this resource that will correspond to groups
                # in *this* database.
                group_ids = []
                for gname in resource_s['groups']:
                    group = groups.get_by_name(gname, assert_exists=False)
                    if not group:
                        group = groups.create(gname)
                        log.info("Created group: {0!r}".format(group))
                    else:
                        log.info("Found existing group: {0!r}".format(group))
                        
                    group_ids.append(group.id)
                
                # First we should see if there is a match for the id and name; we can't rely on name alone since
                # there is no guarantee of name uniqueness (even with a group)
                resource = None
                resource_candidate = resources.get(resource_s['id'], assert_exists=False)
                if resource_candidate and resource_candidate.name == resource_s['name']:
                    resource = resource_candidate 
                else:
                    # If we find a matching resource (by name) and there is only one then we'll use that.
                    try:
                        resource = resources.get_by_name(resource_s['name'], assert_single=True, assert_exists=True)
                    except MultipleResultsFound:
                        log.info("Multiple resource matched name {0!r}, will create a new one.".format(resource_s['name']))
                    except exc.NoSuchEntity:
                        log.debug("No resource found matching name: {0!r}".format(resource_s['name']))
                        pass
                    
                resource_attribs = ('name', 'addr', 'description', 'notes', 'tags')
                resource_attribs_update = dict([(k,v) for (k,v) in resource_s.items() if k in resource_attribs])
                
                if resource:
                    (resource, modified) = resources.modify(resource.id, group_ids=group_ids, **resource_attribs_update)
                    # (yes, we are overwriting 'resource' var with new copy returned from this method)
                    log.info("Updating existing resource: {0!r} (modified: {1!r})".format(resource, modified))
                    if modified and modified != ['group_ids']:
                        if not self.force:
                            raise RuntimeError("Refusing to modify existing resource attributes {0!r} on {1!r} (use 'force' to override this).".format(modified, resource))
                        else:
                            log.warning("Overwriting resource attributes {0!r} on {1!r}".format(modified, resource))
                else:
                    # We will just assume that we need to create the resource.  Yes, it's possible it'll match an existing
                    # one, but better to build a merge tool than end up silently merging things that are not the same.
                    resource = resources.create(group_ids=group_ids, **resource_attribs_update)
                    log.info("Created new resource: {0!r}".format(resource))
                
                # Add the passwords
                for password_s in resource_s['passwords']:
                    
                    password_attribs = ('username', 'description', 'password', 'tags')
                    password_attribs_update = dict([(k,v) for (k,v) in password_s.items() if k in password_attribs])
                
                    # Look for a matching password.  We do know that this is unique.
                    password = passwords.get_for_resource(password_s['username'], password_s['resource_id'], assert_exists=False)
                    if password:
                        (password, modified) = passwords.modify(password_id=password.id, **password_attribs_update)
                        # (Yeah, we overwrite password object.)
                        log.info("Updating existing password: {0!r} (modified: {1!r})".format(password, modified))
                        
                        non_pw_modified = set(modified) - set(['password'])
                        if not modified:
                            log.debug("Password row not modified.")
                        else:
                            log.debug("Password modified: {0!r}".format(modified))
                         
                        # If anything changed other than password, we need to ensure that force=true
                        if non_pw_modified:
                            if not self.force:
                                raise RuntimeError("Refusing to modify existing password attributes {0!r} on {1!r} (use 'force' to override this).".format(non_pw_modified, password))
                            else:
                                log.warning("Overwriting password attributes {0!r} on {1!r}".format(non_pw_modified, password))
                    else:
                        password = passwords.create(resource_id=resource.id, **password_attribs_update)
                        log.info("Creating new password: {0!r}".format(password))
                
                
                # This probably isn't necessary as all the DAO methods should also flush session, but might as well.
                session.flush()
                
        except:
            session.rollback()
            raise
        
    
class YamlImporter(DictImporter):
    
    def __init__(self, use_tags=True, force=False):
        super(YamlImporter, self).__init__(force=force)
        self.use_tags = use_tags
                
    def execute(self, stream):
        """
        """
        if not hasattr(stream, 'read'):
            raise TypeError("stream must be a file-like object.")
        
        
        if not self.use_tags:
            LoaderClass = yaml.SafeLoader
        else:
            LoaderClass = yaml.Loader
            
        structure = yaml.load(stream=stream, Loader=LoaderClass)
        self.from_structure(structure)
    
class GpgYamlImporter(YamlImporter):
    
    def __init__(self, passphrase, use_tags=True, force=False):
        super(GpgYamlImporter, self).__init__(use_tags=use_tags,
                                              force=force)
        self.passphrase = passphrase
    
    def execute(self, stream):
        """
        """
        gpg = GpgAes256()
        decrypted = gpg.decrypt_file(stream, passphrase=self.passphrase)
        
        if not decrypted.ok:
            raise ValueError("Failed to decrypt stream contents. stderr: {0}".format(decrypted.stderr))
        
        # Create a new stream to pass in to the parent
        yaml_stream = StringIO()
        yaml_stream.write(str(decrypted))
        
        # reset our stream
        yaml_stream.seek(0)
        
        super(GpgYamlImporter, self).execute(yaml_stream)