import glob
import re
import os
import os.path
import hashlib
import binascii
from io import BytesIO

from paver.easy import task, cmdopts, needs, sh, info, error
from paver.tasks import BuildFailure
from paver.path import path
from Crypto.Random import get_random_bytes

import pkg_resources
try:
    pkg_resources.get_distribution("ensconce")
except:
    raise BuildFailure("This pavement script must be run from within a configured virtual environment.")

from alembic import command
from Crypto.Random import get_random_bytes

from ensconce.util.paver.tasks import *
from ensconce.config import init_config, init_logging, config
from ensconce import model
from ensconce.model import init_model, meta
from ensconce.model import migrationsutil
from ensconce.dao import groups as groups_dao
from ensconce.crypto import util as crypto_util
from ensconce.export import GpgYamlImporter, GpgYamlExporter

from tests.data import populate

@task
def setup_app(options):
    """ Dependency task to initialize runtime configuration. """
    init_config()
    init_logging()

@task
@cmdopts([('drop', 'D', 'Drop the existing database before initializing')])
@needs('setup_app')
def init_db(options):
    """
    Initialize the database.

    Supported options:
    - drop: True to drop the existing database before initializing.
    """
    init_model(config, drop=getattr(options.init_db, 'drop', False))
    
@task
@needs('setup_app')
def upgrade_db(options):
    """
    Upgrades database to latest (head) revision.
    """
    init_model(config, check_version=False)
    cfg = migrationsutil.create_config()
    command.upgrade(cfg, revision="head")
    
@task
@needs(['setup_app', 'init_db'])
def test_data(options):
    """
    Erases database and replaces contents with test data.
    (This will only work if debug is on and debug secret key is set.)
    """
    if not config['debug'] or not config['debug.secret_key']:
        raise BuildFailure("This target only works with debug=True and debug.secret_key set")
    else:
        secret_key_file = config.get('debug.secret_key')
        crypto_util.load_secret_key_file(secret_key_file)
    
    #init_model(config)
    data = populate.TestDataPopulator()
    data.populate()

@task
@needs(['setup_app', 'init_db'])
def init_crypto(options):
    """
    Interactive target to initialize the database with a new crypto passphrase.
    """
    print "Initializing crypto for an empty database."
    if crypto_util.has_encrypted_data():
        raise BuildFailure("Database has existing encrypted contents; use the 'rekey' target instead.")

    passphrase = raw_input("Passphrase: ")
    print "The database will be initialized with the passphrase between the arrows: --->%s<---" % passphrase
    print "The MD5 of the passphrase you entered is: %s" % hashlib.md5(passphrase).hexdigest()
    
    confirm = raw_input("Type 'YES' to confirm passphrase and MD5 are correct: ")
    if confirm != 'YES':
        raise ValueError("You must enter 'YES' to proceed.")
    
    salt = get_random_bytes(16)
    key = crypto_util.derive_key(passphrase=passphrase, salt=salt)
    crypto_util.initialize_key_metadata(key=key, salt=salt, force_overwrite=False)
    
    print "Database key metadata has been initialized.  Your application is ready for use."
    if config.get('debug'):
        print "The new key is: %s%s" % (binascii.hexlify(key.encryption_key), binascii.hexlify(key.signing_key))

    print "*************************************************************"
    print "IMPORTANT"
    print "Make sure your database master passphrase is stored somewhere"
    print "outside of Ensconce."
    print ""
    print "There is no recovery mechanism for this passphrase (or for "
    print "your database, should you lose it.)"
    print "*************************************************************"    
    
@task
@needs(['setup_app'])
def setup_crypto_state():
    """
    Initialize the crypto engine for already-crypto-configured database.
    """
    if config['debug'] and config['debug.secret_key']:
        crypto_util.load_secret_key_file(config['debug.secret_key'])
    else:
        passphrase = raw_input("Database Master Passphrase: ")
        crypto_util.configure_crypto_state(passphrase)


@task
@needs(['setup_app', 'init_db', 'setup_crypto_state'])
@cmdopts([('groups=', 'g', 'Comma-separated group names to export.'),
          ('groupfile=', 'G', 'A file containing group names (1 per line) to export.'),
          ('file=', 'f', 'Filename to use for single-file export.'),
          ('dir=', 'd', 'Directory in which to put the resulting GPG-encrypted YAML files (one per group).')])
def export_data(options):
    """
    Interactive target to export GPG-encrypted YAML file(s) for specified group(s).
    """
    try:
        dirpath = options.export_data.dir
    except AttributeError:
        dirpath = None
    
    try:
        singlefile = options.export_data.file
    except AttributeError:
        singlefile = None
    
    if dirpath is None and singlefile is None:
        raise BuildFailure('One of --dir/-d or --file/-f is required.')
    elif dirpath is not None and singlefile is not None:
        raise BuildFailure('The --dir/-d or --file/-f are mutually exclusive')
    
    try:
        grouplist = options.export_data.groups
    except AttributeError:
        grouplist = None
        
    try:
        groupfile = options.export_data.groupfile
    except AttributeError:
        groupfile = None
    
    if groupfile is None and grouplist is None:
        raise BuildFailure("One of --groupfile/-G or --groups/-g options must be specified.")
    elif groupfile is not None and grouplist is not None:
        raise BuildFailure("The --groupfile/-G and --groups/-g options are mutually exclusive.")
    
    # First read in the groups by either comma-separating the list or by
    if grouplist: 
        group_names = re.split(r'\s*,\s*', grouplist)
    else:
        with open(groupfile, 'r') as fp:
            group_names = [l.strip() for l in fp if l.strip() != '' and not l.strip().startswith('#')]
            
    # Check these against the database.  Fail fast.
    groups = [groups_dao.get_by_name(gn, assert_exists=True) for gn in group_names]
    
    passphrase = raw_input("GPG Passphrase for export file(s): ")
    
    if singlefile:
        group_ids = [g.id for g in groups]
        print "Exporting groups {0!r} to file: {1}".format(group_names, singlefile)
        exporter = GpgYamlExporter(use_tags=False, passphrase=passphrase,
                                   resource_filters=[model.GroupResource.group_id.in_(group_ids)]) # @UndefinedVariable
        with open(singlefile, 'w') as output_file:
            exporter.export(stream=output_file)
    else:
        # Iterate over the groups.  Export file per group.
        for g in groups:
            exporter = GpgYamlExporter(use_tags=False, passphrase=passphrase,
                                       resource_filters=[model.GroupResource.group_id==g.id]) # @UndefinedVariable
            fn='group-{0}-export.pgp'.format(re.sub('[^\w\-\.]', '_', g.name))
            print "Exporting group '{0}' to file: {1}".format(g.name, fn)
            with open(os.path.join(dirpath, fn), 'w') as output_file:
                exporter.export(stream=output_file)
    
@task
@needs(['setup_app', 'init_db', 'setup_crypto_state'])
@cmdopts([('dir=', 'd', 'A directory containing GPG YAML files (ending with .pgp) to import. ALL MUST HAVE SAME PASSPHRASE.'),
          ('file=', 'f', 'The GPG YAML file to import.'),
          ('force', 'F', 'Whether to force unrecoverable overwrite of duplicate data.')])
def import_data(options):
    """
    Interactive target to import a GPG-encrypted database export (or group export).
    
    If multiple files are specified these are imported in a single transaction.
    """
    try:
        force = options.import_data.force
    except AttributeError:
        force = False
        
    try:
        filepath = options.import_data.file
    except AttributeError:
        filepath = None
            
    try:
        dirpath = options.import_data.dir
    except AttributeError:
        dirpath = None
    
    if filepath is None and dirpath is None:
        raise BuildFailure("Must specify a file path (-f/--file) or directory (-d/--dir) to YAML file(s).")
    elif filepath is not None and dirpath is not None:
        raise BuildFailure("File path (-f/--file) and directory (-d/--dir) are mutually exclusive.")

    if dirpath is not None:
        filenames =  glob.glob(os.path.join(os.path.abspath(dirpath), '*.pgp'))
    else:
        filenames = [os.path.abspath(filepath)]
    
    print "Importing GPG-encrypted YAML file(s) into database."
    
    if force:
        print "DANGER: Overwriting any data collisions (unrecoverable)."
    
    passphrase = raw_input("GPG Passphrase (for all files): ")
    session = meta.Session()
    
    for fn in filenames:
        print "------------------------------------------------------------------------------"
        print "Importing from: {0}".format(fn)
        print "------------------------------------------------------------------------------"
        if not os.path.exists(fn):
            raise BuildFailure("File does not exist: {0}".format(fn))
        
        try:
            importer = GpgYamlImporter(passphrase=passphrase, force=force)
            with open(fn, 'r') as fp:
                importer.execute(fp)
        except:
            print "------------------------------------------------------------------------------"
            print "ERROR! Rolling back entire import."
            print "------------------------------------------------------------------------------"
            session.rollback()
            raise
        else:
            session.commit()


@task
@needs(['setup_app', 'init_db'])
def rekey(options):
    """
    Interactive target to change the passphrase for the database.
    """
    info("This is an EXTREMELY DANGEROUS activity.")
    info("Backup your database first.")
    
    curr_passphrase = raw_input("Current passphrase: ")
    
    crypto_util.configure_crypto_state(curr_passphrase)
    
    new_passphrase = raw_input("New passphrase: ")
    confirm = raw_input("MD5 of passphrase is %s (type \"YES\" to confirm): " % hashlib.md5(new_passphrase).hexdigest())
    if confirm != 'YES':
        raise ValueError("You must enter 'YES' to proceed.")
    
    if crypto_util.has_encrypted_data():
        confirm = raw_input("There is existing encrypted data in the database.  Type 'REKEY' to proceed with re-encryption: ")
        if confirm != 'REKEY':
            raise ValueError("You must enter 'REKEY' to proceed.")
    
    # Use the same salt as previous key
    new_key = crypto_util.derive_configured_key(new_passphrase)
    
    crypto_util.replace_key(new_key=new_key, force=True)
    
    info("Re-encryption completed successfully.")
    
    if config.get('debug'):
        print "The new key is: %s%s" % (binascii.hexlify(new_key.encryption_key), binascii.hexlify(new_key.signing_key))
