"""
Task functions that the server needs to run in daemon threads (on interval, etc.) 
"""
import os
import os.path
import time
import threading
from datetime import datetime
from io import BytesIO

from ensconce import exc
from ensconce.config import config
from ensconce.export import GpgYamlExporter
from ensconce.dao import passwords
from ensconce.autolog import log

class DaemonTask(object):
    def __init__(self, func, interval=0.1, threads=1, wait_first=False, stopped=None):
        self.func, self.interval, self.thread_count = func, interval, threads
        self.wait_first = wait_first
        self.threads = []
        if stopped is None:
            stopped = threading.Event()
        self.stopped = stopped
    
    @property
    def running(self):
        return any(t.is_alive() for t in self.threads)
    
    def run(self):
        
        if self.wait_first and not self.stopped.is_set():
            self.stopped.wait(self.interval)
            
        while not self.stopped.is_set():
            try:
                self.func()
            except:
                log.exception("Error executing daemon function.")
            
            if self.interval:
                self.stopped.wait(self.interval)
    
    def start(self):
        self.stopped.clear()
        self.threads[:] = []
        for i in range(self.thread_count):
            t = threading.Thread(target=self.run)
            t.name = "%s-%s" % (self.func.__name__, i + 1)
            t.daemon = True
            t.start()
            self.threads.append(t)
    
    def stop(self):
        self.stopped.set()
        for i in range(50):
            self.threads[:] = [t for t in self.threads if t.is_alive()]
            if self.threads:
                time.sleep(0.1)
            else:
                break
        else:
            log.warning("not all daemons have been joined: %r" % (self.threads,))

def remove_old_session_files():
    cutoff = int(time.time() - 60 * config["sessions.timeout"])
    cutoff_dt = datetime.fromtimestamp(cutoff)
    log.debug("Checking for sessions older than {0}".format(cutoff_dt.strftime('%H:%M:%S')))
    for fname in os.listdir(config["sessions.storage_path"]):
        if not fname.startswith("."):
            try:
                fpath = os.path.join(config["sessions.storage_path"], fname)
                if os.stat(fpath).st_atime < cutoff:
                    log.debug("Removing stale session: {0}".format(fpath))
                    os.remove(fpath)
            except:
                log.exception("Error removign session: {0}".format(fname))
                pass
    
def backup_database():
    """
    Backups entire database contents to a YAML file which is encrypted using the password
    from a specified mapped password in the database.
    """
    try:
        dir_mode = int(config.get('backups.dir_mode', '0700'), 8)
        file_mode = int(config.get('backups.file_mode', '0600'), 8)
         
        # Before we do anything, validate the configuration.
        if not os.path.exists(config['backups.path']):
            # Attempt to make the directories.
            os.makedirs(config['backups.path'], mode=dir_mode)
        
        if not config.get('backups.encryption.password_id'):
            raise exc.ConfigurationError("Cannot backup without configured password_id (backups.encryption.password_id)")
        
        try:
            pw = passwords.get(config['backups.encryption.password_id'])
        except exc.NoSuchEntity as x:
            raise exc.ConfigurationError("Configured backups.encryption.password_id does not exist in database: {0}".format(x))
        
        
        backup_fname = datetime.now().strftime('backup-%Y-%m-%d-%H-%M.gpg')
        
        msg = "Backing up database to {fname}, secured by password id={pw.id}, resource={resource.name}[{resource.id}]"
        log.info(msg.format(fname=backup_fname, pw=pw, resource=pw.resource))
        
        exporter = GpgYamlExporter(passphrase=pw.password_decrypted,
                                   use_tags=True,
                                   include_key_metadata=True)
        
        encrypted_stream = BytesIO()
        exporter.export(stream=encrypted_stream)
        encrypted_stream.seek(0) # Just to ensure it's rewound
                            
        backup_file = os.path.join(config['backups.path'], backup_fname)
        with open(backup_file, 'w') as fp:
            fp.write(encrypted_stream.read())
            
        os.chmod(backup_file, file_mode)
    except:
        log.critical("Error backing up database.", exc_info=True)
        raise
    
def remove_old_backups():
    # Convert config value of 'days' into 'seconds'
    cutoff = int(time.time() - (60 * 60 * 24) * config["backups.remove_older_than_days"])
    cutoff_dt = datetime.fromtimestamp(cutoff)
    if os.path.exists(config['backups.path']):
        log.debug("Checking for backups older than {0}".format(cutoff_dt.strftime('%m/%d %H:%M:%S')))
        for fname in os.listdir(config["backups.path"]):
            if not fname.startswith("."):
                try:
                    fpath = os.path.join(config["backups.path"], fname)
                    if os.stat(fpath).st_mtime < cutoff:
                        log.debug("Removing old backup: {0}".format(fpath))
                        os.remove(fpath)
                except:
                    log.exception("Error removing old backup file: {0}".format(fname))
                    pass
    else:
        log.error("Unable to remove old backups; backup path does not exist: {0}".format(config['backups.path']))