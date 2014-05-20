"""The application's model objects"""
import os.path
import warnings
from datetime import datetime, timedelta
import uuid
import abc
import binascii

import pytz

from sqlalchemy import orm, engine_from_config
from sqlalchemy.orm import attributes
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.sql import select, and_
from sqlalchemy import (Table, Column, PickleType, ForeignKey, Integer,
                        DateTime, PassiveDefault, LargeBinary,
                        ForeignKeyConstraint, String, Boolean, Text,
                        UniqueConstraint, BigInteger)

from alembic import command

from ensconce.exc import ConfigurationError, DatabaseVersionError
from ensconce.autolog import log
from ensconce.model import meta, migrationsutil
from ensconce.crypto import engine
from ensconce.model import satypes
from ensconce.util import pwhash

def init_model(config, drop=False, check_version=True):
    """
    Initializes the tables and classes of the model using specified engine.

    You must call this method before using any of the tables or classes in
    the model!

    :param config: The application configurat    ion object, where SA config is prefixed with "sqlalchemy."
    :type config: dict
    
    :param drop: Whether to drop the tables first.
    :type drop: bool
    
    :param check_version: Whether to ensure that the database version is up-to-date.
    :type check_version: bool
    """
    engine = engine_from_config(config)
    sm = orm.sessionmaker(autoflush=True, autocommit=False, bind=engine)
    meta.engine = engine
    meta.Session = orm.scoped_session(sm)
    
    alembic_cfg = migrationsutil.create_config()

    # Check to see whether the database has already been created or not.
    # Based on this, we know whether we need to upgrade the database or mark the database
    # as the latest version.
    
    inspector = Inspector.from_engine(engine)
    # We choose an arbitrary table name here to see if database objects have been created
    db_objects_created = (groups_table.name in inspector.get_table_names())
    fresh_db = False
    if not db_objects_created:
        log.info("Database apears uninitialized, creating database tables")
        meta.metadata.create_all(engine, checkfirst=True)
        fresh_db = True
    elif drop:
        log.info("Dropping database tables and re-creating.")
        meta.metadata.drop_all(engine, checkfirst=True)
        meta.metadata.create_all(engine)
        fresh_db = True
        
    if fresh_db:
        command.stamp(alembic_cfg, "head")
    else:
        # Existing model may need upgrade.
        if check_version:
            latest = migrationsutil.get_head_version()
            installed = migrationsutil.get_database_version()
            if latest != installed:
                raise DatabaseVersionError("Installed database ({0}) does not match latest available ({1}). (Use the `paver upgrade_db` command.)".format(installed, latest))
        else:
            log.info("Skipping database upgrade.")
    
    if check_version:
        # We only want to run this code if this is a normal version-checking model initialization.
        # Basically we do *not* want to run this when we are upgrading the database.
        # (This may need to get refactored to be clearer.)
        #
        # Special check for acl data (this is kinda kludgy, but app won't work if this row isn't here.)
        s = meta.Session()
        a = s.query(Access).get(1)
        if not a:
            # Can't import this at top-level due to circular
            from ensconce import acl
            a = Access()
            a.description = 'Administrator'
            a.level = acl.ALL_ACCESS
            s.add(a)
            s.commit() # We really do want to commit immediately in this particular case.

def set_entity_attributes(entity, update_attributes, encrypted_attributes=None, hashed_attributes=None):
    """
    A convenience method to set attributes (column values) on an entity and 
    return the attributes which were actually modified.
    
    :param obj: The entity object being updated.
    :param update_attributes: A dict of attributes that should be set on this object.
    :param encrypted_attributes: A list of any attributes that are encrypted (and need
                            to be set using the *_decrypted method variant).
    :return: A list of modified attributes (column names).
    :rtype: list
    """
    if encrypted_attributes is None:
        encrypted_attributes = []
    
    if hashed_attributes is None:
        hashed_attributes = []
        
    for (attrib, value) in update_attributes.items():
        if attrib not in encrypted_attributes and attrib not in hashed_attributes: 
            setattr(entity, attrib, value)
    
    for attrib in encrypted_attributes:
        if attrib in update_attributes:
            value = update_attributes[attrib]
            decrypted_attrib = attrib + '_decrypted'
            if value != getattr(entity, decrypted_attrib):
                setattr(entity, decrypted_attrib, value)

    for attrib in hashed_attributes:
        if attrib in update_attributes:
            value = update_attributes[attrib]
            if value is None:
                setattr(entity, attrib, value)
            elif not pwhash.compare(getattr(entity, attrib), value):
                setattr(entity, attrib, pwhash.obscure(value)) # Using default hashtype
                
    # Use SQLAlchemy's cool get_history method:
    # http://docs.sqlalchemy.org/en/rel_0_7/orm/session.html?highlight=get_history#sqlalchemy.orm.attributes.History
    modified = []
    for attrib in update_attributes.keys():
        hist = attributes.get_history(entity, attrib)
        if hist.has_changes():
            modified.append(attrib)
    
    return modified
    
class Entity(object):
    """
    A base class for the entities that have ID and label properties.
    """
    __metaclass__ = abc.ABCMeta
    
    def __unicode__(self):
        return u'{0}({1},{2})'.format(self.__class__.__name__, self.id, self.label)
    
    def __repr__(self):
        return '<{0} id={1!r} label={2!r}>'.format(self.__class__.__name__, self.id, self.label)

    # Intentionally not a property since properties can't get put into SA queries.
    @classmethod
    def object_type(cls):
        return cls.__name__
    
    @abc.abstractproperty
    def label(self):
        pass
    
    @abc.abstractmethod
    def to_dict(self):
        pass
    
    def auditlog(self, code=None, order_by=None, limit=None):
        """
        Returns a database query to fetch audit logs for this resource.
        
        The response object is a bound SA query with a filter on this object.
        Convenience params are provided for code and order by clauses.
        
        :param code: The auditlog code. (Can also be specified by calling .filter() on response.)
        :param order_by: The order by expression to use. (Can also be specified by calling .order_by() on response.)
        :param limit: The limit for num of rows query should return. (Can also be specified by calling .limit() on response.)
        """
        if not self.id:
            raise ValueError("Unable to lookup auditlog entries; object has no ID: {0!r}".format(self))
        
        session = meta.Session()
        t = auditlog_table
        q = session.query(AuditlogEntry).filter(and_(t.c.object_type==self.object_type(), t.c.object_id==self.id))
        if code:
            q = q.filter(t.c.code==code)
        if order_by:
            q = q.order_by(order_by)
        if limit:
            q = q.limit(limit)
            
        return q
        
    def creation(self):
        """
        Does an auditlog query to lookup the operator that created this entity.
        """
        pass
    
    def last_modification(self):
        """
        Does an auditlog query to determine when this record was last modified.
        """
        
       
class Operator(Entity):
    @property
    def label(self):
        return self.username

    def to_dict(self, include_access=False):
        d = dict(id=self.id,
                 username=self.username,
                 access_id=self.access_id,
                 externally_managed=self.externally_managed)
        if include_access:
            d['access'] = self.access.to_dict()
        return d
    
class Password(Entity):
    
    @property
    def label(self):
        return self.username
    
    @property
    def password_decrypted(self):
        return engine.decrypt(self.password)

    @password_decrypted.setter
    def password_decrypted(self, cleartext):
        self.password = engine.encrypt(cleartext)
        
    def to_dict(self, decrypt=True, include_resource=False, include_history=False):
        """
        Converts password to a dict.
        
        :param decrypt: Whether to include decrypted password.
        :param include_resources: Whether to include associated parent resource.
        :param include_history: Whether to add password history rows.
        """        
        d = dict(id=self.id,
                 username=self.username,
                 resource_id=self.resource_id,
                 description=self.description,
                 tags=self.tags, # XXX: split?
                 )
        if decrypt:
            d['password'] = self.password_decrypted
            
        if include_resource:
            d['resource'] = self.resource.to_dict()
            
        if include_history:
            d['history'] = [h.to_dict() for h in self.history.order_by(password_history_table.c.modified.desc())]
            
        return d

class PasswordHistory(Entity):
    
    @property
    def label(self):
        if self.subject:
            return self.subject.username
        else:
            return u"(unbound pw hist)"
        
    @property
    def password_decrypted(self):
        # The unicode conversion *seems* like overkill, but is probably the safe thing to do.
        decrypted = engine.decrypt(self.password)
        if decrypted is not None:
            return unicode(decrypted, 'utf-8')
        else:
            return decrypted

    @password_decrypted.setter
    def password_decrypted(self, cleartext):
        self.password = engine.encrypt(cleartext)
        
    def to_dict(self, decrypt=True, include_subject=False):
        """
        :param decrypt: Whether to include decrypted password.
        :param include_subject: Whether to include the parent/subject Password object.
        """
        d = dict(id=self.id,
                 password_id=self.password_id,
                 )
        if decrypt:
            d['password'] = self.password_decrypted
            
        if include_subject:
            d['subject'] = self.subject.to_dict()
        return d
    
    
class Group(Entity):
    @property
    def label(self):
        return self.name
    
    def to_dict(self, include_resources=False, decrypt_resources=False):
        d = dict(id=self.id,
                 name=self.name,
                 )
        if include_resources:
            d['resources'] = [r.to_dict(decrypt=decrypt_resources) for r in self.resources.order_by('name')]
        return d
    
class Resource(Entity):
    """
    """
    @property
    def label(self):
        return self.name
    
    @property
    def notes_decrypted(self):
        decrypted = engine.decrypt(self.notes)
        if decrypted is not None:
            return unicode(decrypted, 'utf-8')
        else:
            return decrypted

    @notes_decrypted.setter
    def notes_decrypted(self, cleartext):
        self.notes = engine.encrypt(cleartext)

    def to_dict(self, decrypt=True, include_passwords=False, decrypt_passwords=False):
        d = dict(id=self.id,
                 group_ids=[g.id for g in self.groups.all()],
                 name=self.name,
                 addr=self.addr,
                 description=self.description,
                 tags=self.tags, # XXX: split?
                 )
        if decrypt:
            d['notes'] = self.notes_decrypted
        if include_passwords:
            d['passwords'] = [p.to_dict(decrypt=decrypt_passwords) for p in self.passwords.order_by(passwords_table.c.username)]
        return d
    
class Access(Entity):
    """
    """
    @property
    def label(self):
        return self.description
    
    def to_dict(self):
        d = dict(id=self.id,
                 level=self.level,
                 description=self.description,
                 )
        return d
    
class GroupResource(object):
    """
    A lookup table row for many-to-many groups-resources relationship.
    """
    pass

class AuditlogEntry(object):
    """
    An entry in the audit log.
    """
    
    def lookup_entity(self):
        """
        Lookup the entity object associated with this audit log row or None if 
        there is no target object.
        """
        if self.object_id is None or self.object_type is None:
            return None
        try:
            clazz = globals()[self.object_type]
        except KeyError:
            raise ValueError("Invalid class object specified in audit log: {0}".format(self.object_type))
        
        session = meta.Session()
        return session.query(clazz).get(self.object_id)
        
    def to_dict(self, include_operator=False):
        d = dict(id=self.id,
                 datetime=self.datetime.strftime('%Y-%m-%d %H:%M:%S'), # TODO: TZ?
                 code=self.code,
                 operator_id=self.operator_id,
                 operator_username=self.operator_username,
                 object_type=self.object_type,
                 object_id=self.object_id,
                 object_label=self.object_label,
                 attributes_modified=self.attributes_modified,
                 comment=self.comment,
                 )
        if include_operator:
            d['operator'] = self.operator.to_dict() if self.operator else None
        return d
    
class KeyMetadata(object):
    """
    An entry in the encryption-key validation/metadata table.
    
    We should probably point out that we're not storing the actual encryption 
    keys in the database, but we do need some mechanism to validate a key
    (and decrypting a random password is not a good one).
    """
    def __repr__(self):
        return '<{0} id={1}>'.format(self.__class__.__name__, self.id)
    
    def to_dict(self, encode=False):
        salt = binascii.hexlify(self.kdf_salt) if encode else self.kdf_salt
        return dict(id=self.id, kdf_salt=salt)
    
# This table exists to store the salt that is used by the KDF to build the keys
# from passphrase.  
key_metadata_table = Table('key_metadata', meta.metadata,
                            Column('id', Integer, primary_key=True, autoincrement=False),
                            Column('validation', satypes.HexEncodedBinary, nullable=False),
                            Column('kdf_salt', satypes.HexEncodedBinary, nullable=False))

operators_table = Table('operators', meta.metadata,
                        Column('id', Integer, primary_key=True),
                        Column('username', String(255), nullable=False, index=True),
                        Column('password', Text, nullable=True),
                        Column('access_id', Integer, ForeignKey('access.id', ondelete="RESTRICT"), index=True, nullable=True),
                        Column('externally_managed', Boolean, default=False, nullable=False),
                        UniqueConstraint('username'),
                        )

passwords_table = Table('passwords', meta.metadata,
                        Column('id', BigInteger, primary_key=True, autoincrement=True),
                        Column('username', String(255), nullable=False, index=True),
                        Column('password', satypes.HexEncodedBinary, nullable=True),
                        Column('resource_id', Integer, ForeignKey('resources.id', ondelete="RESTRICT"), nullable=False, index=True), # TODO: Cascade delete
                        Column('description', Text, nullable=True), # NOT ENCRYPTED
                        Column('expire', DateTime(timezone=pytz.utc), nullable=True, index=True), # Relevant for the future?
                        Column('tags', Text, nullable=True), # NOT ENCRYPTED
                        )

password_history_table = Table('password_history', meta.metadata,
                         Column('id', BigInteger, primary_key=True, autoincrement=True),
                         Column('password_id', Integer, ForeignKey('passwords.id', ondelete="CASCADE"), nullable=False, index=True),
                         Column('modified', DateTime(timezone=pytz.utc), default=datetime.now, nullable=False, index=True),
                         Column('modifier_id', Integer, ForeignKey('operators.id', ondelete="SET NULL"), nullable=True, index=True),
                         Column('modifier_username', String(255), nullable=True), # For when the operators are deleted.
                         Column('password', satypes.HexEncodedBinary, nullable=True)) # Encrypted!
                        
groups_table = Table('groups', meta.metadata,
                     Column('id', Integer, primary_key=True),
                     Column('name', String(255), nullable=False, index=True, unique=True))

resources_table = Table('resources', meta.metadata,
                        Column('id', Integer, primary_key=True),
                        Column('name', String(255), nullable=False, index=True),
                        Column('addr', String(255), nullable=True, index=True),
                        Column('description', Text, nullable=True),
                        Column('notes', satypes.HexEncodedBinary, nullable=True),
                        Column('tags', Text, nullable=True), # NOT ENCRYPTED
                        )

group_resources_table = Table('group_resources', meta.metadata,
                              Column('group_id', Integer, ForeignKey('groups.id', ondelete="RESTRICT"), primary_key=True), # Do *not* orphan resources.
                              Column('resource_id', Integer, ForeignKey('resources.id', ondelete="CASCADE"), primary_key=True))

auditlog_table = Table('auditlog', meta.metadata,
                       Column('id', BigInteger, primary_key=True),
                       Column('datetime', DateTime(timezone=pytz.utc), default=datetime.now, nullable=False, index=True),
                       Column('code', String(255), nullable=False, index=True),
                       Column('operator_id', Integer, ForeignKey('operators.id', ondelete="SET NULL"), nullable=True, index=True),
                       Column('operator_username', String(255), nullable=True, index=True),
                       Column('object_type', String(255), nullable=True, index=True),
                       Column('object_id', BigInteger, nullable=True, index=True),
                       Column('object_label', Text, nullable=True),
                       Column('attributes_modified', satypes.SimpleList, nullable=True),
                       Column('comment', Text, nullable=True))

access_table = Table('access', meta.metadata,
                     Column('id', Integer, primary_key=True, nullable=False),
                     Column('level', BigInteger, nullable=False),
                     Column('description', Text, nullable=True))


orm.mapper(Operator, operators_table, properties={
    'access': orm.relationship(Access),
    'auditlog': orm.relationship(AuditlogEntry, lazy="dynamic", backref="operator")
})

orm.mapper(Password, passwords_table, properties={
    'history': orm.relationship(PasswordHistory, backref='subject', lazy="dynamic", cascade="all,delete")
})

orm.mapper(PasswordHistory, password_history_table, properties={
    'modifier': orm.relationship(Operator)
})

orm.mapper(Group, groups_table, properties={
    'resources': orm.relationship(Resource, secondary=group_resources_table, lazy="dynamic")
})

orm.mapper(Resource, resources_table, properties={
    'groups': orm.relationship(Group, secondary=group_resources_table, lazy="dynamic"),
    'passwords':  orm.relationship(Password, backref="resource", lazy="dynamic")
})

orm.mapper(Access, access_table, properties={
    'operators': orm.relationship(Operator, lazy="dynamic"),
})

orm.mapper(GroupResource, group_resources_table) # We probably don't need this mapped to an object since it's only a secondary table?

orm.mapper(AuditlogEntry, auditlog_table)

orm.mapper(KeyMetadata, key_metadata_table)
