"""
Database crypto.
"""
import binascii

from sqlalchemy import func, and_
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from Crypto.Random import get_random_bytes
from Crypto.Protocol.KDF import PBKDF2

from ensconce import model, exc
from ensconce.model import meta
from ensconce.crypto import engine, state, MasterKey, CombinedMasterKey
from ensconce.autolog import log

def configure_crypto_state(passphrase):
    """
    Convenience function to sets up the shared crypto state using the specified passphrase.
    
    This function assumes that the metadata for this key has already been initialized.
    
    :raise ensconce.exc.MissingKeyMetadata: If the metadata row does not exist yet.
    :raise ensconce.exc.MultipleKeyMetadata: If there are multiple metadata rows.
    :raise ensconce.exc.UnconfiguredModel: If we can't create an SA session.
    """
    key = derive_configured_key(passphrase)
    # TODO: Consider moving the key validation in here instead.
    state.secret_key = key

def derive_configured_key(passphrase):
    """
    Derives a key with specified passphrase and stored salt using PBKDF2 algorithm.
    
    :param passphrase: A passphrase string of any length, will be used to create the keys.
    :type passphrase: str
    :return: The encryption and signing key set.
    :rtype: ensconce.crypto.MasterKey
    
    :raise ensconce.exc.MissingKeyMetadata: If the metadata row does not exist yet.
    :raise ensconce.exc.MultipleKeyMetadata: If there are multiple metadata rows.
    :raise ensconce.exc.UnconfiguredModel: If we can't create an SA session.
    """
    if isinstance(passphrase, unicode):
        passphrase = passphrase.encode("utf-8")
        
    if not isinstance(passphrase, str):
        raise TypeError("Passphrase must be bytestring.")
    
    if meta.Session is None:
        raise exc.UnconfiguredModel()
    
    # We assume that the mission is to look up an existing key.
    session = meta.Session()
    try:
        key_info = session.query(model.KeyMetadata).one()
        salt = key_info.kdf_salt
    except NoResultFound:
        raise exc.MissingKeyMetadata()
    except MultipleResultsFound:
        raise exc.CryptoError("Multiple key metadata rows are not supported.")
    
    return derive_key(passphrase, salt)

def derive_key(passphrase, salt):
    """
    Creates a key from passphrase and salt using PBKDF2.
    
    :param passphrase: A passphrase string of any length, will be used to create the keys.
    :type passphrase: str
    
    :param salt: The initialization salt.  This does not need to be kept secret, but should
                    be different for each installation of the software to protect against 
                    precomputing-hash attacks (ranbow tables).  The standard recommends this
                    be at least 64-bits, so we will throw an exception if it is smaller.
    :type salt: str
    
    :return: The encryption and signing key set.
    :rtype: ensconce.crypto.MasterKey
    """
    if isinstance(passphrase, unicode):
        passphrase = passphrase.encode("utf-8")
        
    if not isinstance(passphrase, str):
        raise TypeError("Passphrase must be bytestring.")
    
    if not isinstance(salt, str):
        raise TypeError("Salt must be bytestring.")
    
    if len(salt) < 8:
        raise ValueError("Salt must be at least 64 bits (8 bytes).")
    
    return CombinedMasterKey(PBKDF2(passphrase, salt, dkLen=64))
    
def load_secret_key_file(secret_key_file):
    """
    Loads a secret key from a file and initializes the engine with this key.
    
    This is designed for use in development/debugging and should NOT be used 
    in production, if you value the encrypted database data.
    
    :param secret_key_file: The path to a file containing the 32-byte secret key.
    :type secret_key_file: str
    
    :raise ensconce.exc.CryptoNotInitialized: If the engine cannot be initialized.
    """
    try:
        with open(secret_key_file) as fp:
            key_bytes = binascii.unhexlify(fp.read().strip())
            log.info("Using DEBUG secret.key from file: {0}".format(secret_key_file))
            try:
                secret_key = CombinedMasterKey(key_bytes)
                validate_key(key=secret_key)
            except exc.MissingKeyMetadata:
                log.info("Writng out DEBUG secret.key to key metadata row.")
                initialize_key_metadata(key=secret_key, salt=get_random_bytes(16))
            state.secret_key = secret_key
    except:
        log.exception("Unable to initialize secret key from file.")
        raise exc.CryptoNotInitialized("Crypto engine has not been initialized.")
    
def validate_key(key):
    """
    Checks the key against an encrypted blob in the database.
    
    :param key: The master key to check.
    :type key: ensconce.crypto.MasterKey
    
    :raise ensconce.exc.MissingKeyMetadata: If the metadata row does not exist yet.
    :raise ensconce.exc.MultipleKeyMetadata: If there are multiple metadata rows.
    :raise ensconce.exc.UnconfiguredModel: If we can't create an SA session.
    """
    if meta.Session is None:
        raise exc.UnconfiguredModel()
    
    session = meta.Session()
    try:
        key_info = session.query(model.KeyMetadata).one()
        #log.debug("Got bytes for validation: {0!r}".format(key_info.validation))
        try:
            decrypted = engine.decrypt(key_info.validation, key=key)
            #log.debug("Decrypts to: {0!r}".format(decrypted))
        except exc.CryptoAuthenticationFailed:
            log.exception("Validation fails due to error decrypting block.")
            return False
        else:
            return True
    except NoResultFound:
        raise exc.MissingKeyMetadata()
    except MultipleResultsFound:
        raise exc.CryptoError("Multiple key metadata rows are not supported.")
    except:
        log.exception("Error validating encryption key.")
        raise

    
def has_encrypted_data():
    """
    Whether there is any encrypted data in the database.
    
    The answer to this question can help determine whether it's ok to change
    encryption keys w/o re-encrypting database, etc.
    
    :raise ensconce.exc.UnconfiguredModel: If we can't create an SA session.
    """
    try:
        session = meta.Session()
        p_t = model.passwords_table
        r_t = model.resources_table
        pw_cnt = session.query(func.count(p_t.c.id)).filter(and_(p_t.c.password != None, p_t.c.password != '')).scalar() 
        rs_cnt = session.query(func.count(r_t.c.id)).filter(and_(r_t.c.notes != None, r_t.c.notes != '')).scalar()
    except:
        log.exception("Error checking for encrypted database data.")
        raise
    
    return (pw_cnt > 0 or rs_cnt > 0)

def create_key_validation_payload(key=None):
    """
    Utility function to create the encrypted payload that we will late use for key validation.
    
    TODO: Consider replacing with something smarter.  HMAC?
    """
    some_bytes = get_random_bytes(256)
    return engine.encrypt(some_bytes, key=key)

def clear_key_metadata():
    """
    This is a utility function (built for testing) that just removes any key_metadata
    rows (with the intent that they will get re-created during crypto initialization phase).
    
    :raise ensconce.exc.UnconfiguredModel: If we can't create an SA session.
    """
    if meta.Session is None:
        raise exc.UnconfiguredModel()
    
    session = meta.Session()
    try:
        session.execute(model.key_metadata_table.delete())
        session.commit() # We are deliberately committing early here
    except:
        session.rollback()
        log.exception("Error clearing key metadata table.")
        raise
    
def initialize_key_metadata(key, salt, force_overwrite=False, nested_transaction=False):
    """
    Called when key is first specified to set some database encrypted contents.
    
    This must be run before the crypto engine has been initialized with the secret
    key.
    
    :param key: The new encryption and signing key set.
    :type key: ensconce.crypto.MasterKey
    
    :param salt: The salt to use for the KDF function.  IMPORTANT: This cannot change w/o re-encrypting database.
    :type salt: str
    
    :param force_overwrite: Whether to delete any existing metadata first (dangerous!)
    :type force_overwrite: bool
    
    :param nested_transaction: Whether this is being run within an existing transaction (i.e. do not commit).
    :type nested_transaction: bool
    
    :raise ensconce.exc.CryptoAlreadyInitialized: If the engine has already been initialized we bail out.
    :raise ensconce.exc.UnconfiguredModel: If we can't create an SA session.
    :raise ensconce.exc.ExistingKeyMetadata: If there is already key metadata (and `force_overwrite` param is not `True`).
    """
    assert isinstance(key, MasterKey)
    assert isinstance(salt, str)
    
    if state.initialized:
        raise exc.CryptoAlreadyInitialized()
    
    if meta.Session is None:
        raise exc.UnconfiguredModel()
    
    session = meta.Session()
    try:
        existing_keys = session.query(model.KeyMetadata).all()
        if len(existing_keys) > 0:
            if force_overwrite:
                for ek in existing_keys:
                    session.delete(ek)
                    log.warning("Forcibly removing existing metadata: {0}".format(ek))
                session.flush()
            else:
                raise exc.ExistingKeyMetadata()
            
        km = model.KeyMetadata()
        km.id = 0 # Chosen to be obviously out of auto-increment "range"
        km.validation = create_key_validation_payload(key=key)
        km.kdf_salt = salt
        session.add(km)
        if not nested_transaction:
            session.commit() # We are deliberately committing early here
        else:
            session.flush()
    except:
        if not nested_transaction:
            # This conditional probably has little effect, since the connection will be in err state anyway
            # until a rollback is issued.
            session.rollback()
        log.exception("Error initializing key metadata")
        raise
        
def replace_key(new_key, force=False):
    """
    Replaces the database key.  If there are encrypted contents in the database, you
    must specify force=True which will *reencrypt* the database contents with the new key.
    
    This is dangerous.
    
    !!!! BACKUP FIRST !!!!
    !!!! STOP WEB SERVER !!!!
    
    :param new_key: The new encryption key.
    :raise ensconce.exc.CryptoNotInitialized: If the engine has not been initialized (with the correct current key).
    :raise ensconce.exc.MissingKeyMetadata: If the metadata row does not exist yet.
    :raise ensconce.exc.MultipleKeyMetadata: If there are multiple metadata rows.
    :raise ensconce.exc.UnconfiguredModel: If we can't create an SA session.
    :raise ensconce.exc.DatabaseAlreadyEncrypted: If database has encrypted data and `force` param is not `True`.
    """
    assert isinstance(new_key, MasterKey)
    
    if not state.initialized:
        raise exc.CryptoNotInitialized()
    
    if meta.Session is None:
        raise exc.UnconfiguredModel()
    
    if has_encrypted_data() and not force:
        raise exc.DatabaseAlreadyEncrypted("Database has existing encrypted data (must specify force to reencrypt existing data).")
    
    session = meta.Session()
    assert session.autocommit == False
    
    with state.key_lock:
        try:
            key_info = session.query(model.KeyMetadata).one()
            
            pass_t = model.passwords_table
            
            # Re-encrypt all of the passwords with the new key.
            for pw in session.query(model.Password).filter(and_(pass_t.c.password != None, pass_t.c.password != '')):
                # Important: set the *encrypted* password here (not password_decrypted)
                pw.password = engine.encrypt(pw.password_decrypted, key=new_key)
                
            session.flush()
            
            ph_t = model.password_history_table
            for pwh in session.query(model.PasswordHistory).filter(and_(ph_t.c.password != None, ph_t.c.password != '')):
                # Important: set the *encrypted* password here (not password_decrypted)
                pwh.password = engine.encrypt(pwh.password_decrypted, key=new_key) 
            
            session.flush()
            
            # Re-encrypt all of the notes fields for resources 
            resources_t = model.resources_table
            for rsc in session.query(model.Resource).filter(and_(resources_t.c.notes != None, resources_t.c.notes != '')):
                # Important: set the *encrypted* password here (not password_decrypted)
                rsc.notes = engine.encrypt(rsc.notes_decrypted, key=new_key)
                
            session.flush()
            
            key_info.validation = create_key_validation_payload(key=new_key)
            
            session.flush()
            
            state.secret_key = new_key
            
        except NoResultFound:
            raise exc.MissingKeyMetadata("No key metadata found; initialize key metadata before replacing key.")
        except MultipleResultsFound:
            raise exc.CryptoError("Multiple key metadata rows are not supported.")
        except:
            session.rollback()
            log.exception("Error replacing key; rolling back transaction.")
            raise
        else:
            session.commit()

