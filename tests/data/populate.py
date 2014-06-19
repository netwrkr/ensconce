# -*- coding: utf-8 -*-
from datetime import datetime
import pytz
import netaddr
import collections

from ensconce import model
from ensconce.model import meta
from ensconce.util import pwhash
from ensconce.autolog import log

from tests.data import sslsamples

class TestDataPopulator(object):

    def __init__(self):
        self.groups = {}
        self.operators = {}
        self.resources = {}
        self.passwords = {}
   
    def _create_operators(self):
        session = meta.Session()
        for username, pw in (('op1', 'pw1'), ('op2', 'pw2'), ('op3', 'pw3')):        
            o = model.Operator()
            o.username = username
            o.password = pwhash.obscure(pw)
            o.access_id = 1 # FIXME: Probably should be creating access levels in data pouplator 
            session.add(o)
            self.operators[o.username] = o
            session.flush()
            log.debug("Created {0}".format(o))
        
    def _create_groups(self):
        session = meta.Session()
        for name in ('First Group', 'Second Group', 'Third Group', 'Fourth Group', 'fifth group', '6th group'):        
            g = model.Group()
            g.name = name
            g.date_created = datetime.now(tz=pytz.utc)
            g.creator = self.operators['op1']
            session.add(g)
            self.groups[name] = g
            session.flush()
            log.debug("Created {0}".format(g))
    
    def _create_resources(self):
        session = meta.Session()
        
        R = collections.namedtuple('Resource', ['name', 'addr', 'description', 'notes', 'tags', 'groups'])
        
        data = (R('host1.example.com', '192.168.1.1', None, 'Encrypted notes', [], ['First Group', 'Second Group']),
                R('host2.example', '192.168.1.2', None, None, ['tagonly'], ['First Group']),
                R('Bikeshed PIN', None, None, 'L-R-L-R-U-D-U-D 123', ['tagprefix:tagone'], ['First Group']),
                R('BoA', '172.16.20.39', 'Online bank', 'The bank picture should be a monkey!', ['tagone', 'tagtwo'], ['First Group', 'Third Group']),
                R(u'faß.de', '10.0.1.1', u'ვეპხის ტყაოსანი შოთა რუსთაველი', u"Sîne klâwen durh die wolken sint geslagen", [], ['6th group', 'First Group']),
                R(u'ԛәлп.com', '10.0.1.2', u'ಬಾ ಇಲ್ಲಿ ಸಂಭವಿಸು ಇಂದೆನ್ನ ಹೃದಯದಲಿ', u"На берегу пустынных волн", [], ['6th group', 'First Group']),
                R('https-server', '127.0.0.1', 'Testing SSL cert/key storage.', None, ['tagtwo', 'tagone'], ['Fourth Group']),
                )
        
        for el in data:
            r = model.Resource()
            r.name = el.name
            r.addr = el.addr
            r.description = el.description
            r.notes_decrypted = el.notes
            if el.tags:
                r.tags = ' '.join(el.tags)
            for gname in el.groups:
                r.groups.append(self.groups[gname])
            session.add(r)
            self.resources[r.name] = r
            session.flush()
            log.debug("Created {0}".format(r))
        
        
    def _create_passwords(self):
        
        session = meta.Session()
        r = self.resources['host1.example.com']
        for i in range(5):
            p = model.Password()
            p.username = 'user{0}'.format(i)
            p.password_decrypted = 'password{0}'.format(i)
            p.description = 'Description Text'
            r.passwords.append(p)
            session.flush()
            log.debug("Added {0} to {1}".format(p, r))
        
        r = self.resources['host2.example']
        for i,un in enumerate(('user', 'root')):
            p = model.Password()
            p.username = un
            p.password_decrypted = 'AxF$#( )#-{0}'.format(i)
            p.description = None
            r.passwords.append(p)
            session.flush()
            log.debug("Added {0} to {1}".format(p, r))
        
        r = self.resources['BoA']
        p = model.Password()
        p.username = 'bankus3r'
        p.password_decrypted = '!MonkeyPass!'.format(i)
        p.description = 'Remember, picture should be a monkey.  Woah, this is not encrypted?'
        p.tags = 'tagprefix2:tagone tagtwo'
        r.passwords.append(p)
        session.flush()
        log.debug("Added {0} to {1}".format(p, r))
        
        
        r = self.resources['https-server']
        p = model.Password()
        p.username = 'ssl.cert'
        p.password_decrypted = sslsamples.keypair1.cert # @UndefinedVariable
        p.description = 'PEM-encoded x509 certificate'
        p.tags = 'tagtwo tagprefix:tagone'
        r.passwords.append(p)
        session.flush()
        log.debug("Added {0} to {1}".format(p, r))
        
        r = self.resources['https-server']
        p = model.Password()
        p.username = 'ssl.key'
        p.password_decrypted = sslsamples.keypair1.key # @UndefinedVariable
        p.description = 'PEM-encoded 2048-bit RSA key'
        p.tags = 'tagprefix'
        r.passwords.append(p)
        session.flush()
        log.debug("Added {0} to {1}".format(p, r))
        
        
    def populate(self):
        session = meta.Session()
        try:
            self._create_operators()
            self._create_groups()
            self._create_resources()
            self._create_passwords()
            session.commit()
        except:
            session.rollback()
            raise
    
    def depopulate(self):
        session = meta.Session()
        try:
            session.execute(model.passwords_table.delete())
            session.execute(model.resources_table.delete())
            session.execute(model.groups_table.delete())
            session.execute(model.operators_table.delete())
            session.commit()
        except:
            session.rollback()
            raise