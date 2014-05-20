Ensconce is an enterprise password manager system, designed to store *shared* passwords in a secure fashion.  Ensconce is 
designed for use by operational teams that need access to the same set of passwords and need to ensure these passwords are
maintained in a single, central location and are only stored encrypted.

Current Features:
 * Passwords and resource notes fields are encrypted in the database with a master key (symmetric).  The key is stored in 
   memory upon application initialization and is used to decrypted the encrypted fields on demand.
 * Organization into Groups (top-level), Resources (e.g. hosts/systems), and Credentials.
 * Authentication backends to LDAP or internal database.  LDAP authenticator can restrict access to specific group(s).
 * Detailed audit logs of view/mod/delete activities.
 * Password history is maintained for credentials.
 * Support for exporting passwords to encrypted file formats.
 * JSON-RPC 2.0 API for reading and modifying passwords.
 
Major Planned Features:
 * Restrictions on password access within the system.  (Currently to restrict by groups, you would need to setup 
   different instances of the password manager and control login access.)
 * More modern UI, enhanced support for large numbers of password groups.

**IMPORTANT:** Ensconce is designed to be a secure password storage system; however, there are a number of considerations 
that affect the overall security fo the system.
1. Ensconce does not protect memory from inspection.  Ensconce, being written in python, does not involve itself in low-level 
   memory access nor does it attempt to conceal the contents of RAM.  It is assumed that an attacker that is one the system
   would be able to see decrypted sensitive data should they have the desire (and necessary understanding of linux, etc.).  Disabling
   access to the /proc filesystem on linux may be desired to make memory inspection more difficult.
2. Relatedly, Ensconce does not stop your operating system from swapping (aka paging), which may result in potentially sensitive
   information being written to disk.  You should consider disable swapping on your OS if hard drive forensics is a concern. (And, 
   of course, if you are running in a VM and using features like snapshots then it is likely you are writing sensitive information
   to the VM storage disc.)
3. The system security will, of course, also be affected by things such as firewalls, selinux, and file permissions, which are beyond the scope of
   this document.
4. Finally, one of the greatest security liabilities in any application is the user.  If users decrypt and export database contents or 
   otherwise make decrypted contents accessible, any benefit of database-level encryption will be lost.
  

Installation
============

Ensconce is designed to be installed using pip or easy_install; however, RPM packaging support is also provided for CentOS 5.x and 6.x to 
simplify installation on those platforms.  Since production setup is simpler from finished packages, we will use that as our example here. 

Building the RPM Packages
-------------------------

These instructions assume CentOS 6.x; if using 5.x you will need to install python26 packages from EPEL.

Ensure you have the necessary tools in your environment:
.. code-block:: none
    shell# yum install rpmbuild buildsys-macros gcc openldap-devel postgresql-devel mysql-devel

Start building the project by creating a virtualenv for your project and installing the dendencies.

.. code-block:: none
    shell$ cd /path/to/ensconce
    shell$ python -m virtualenv env
    shell$ source env/bin/activate
    (env) localhost$ python setup.py develop

Then use the Paver "rpm" task to create your RPM package:

.. code-block:: none
    (env) localhost$ paver rpm

If you are building an RPM of a current development version, you will need to use the "--testing" flag.

.. code-block:: none
    (env) localhost$ paver rpm --testing 

Install from RPM
----------------

1. First install the RPM package itself:
   ```
   shell# yum install /path/to/ensconce-x.x.x-x.rpm
   ```
2. Edit the `/etc/ensconce/settings.cfg` file to specify the configuration options you wish to use.  Inline
   comments should provide details on the meaning of the different options.  You can also consult `/opt/ensconce/defaults.cfg`
   to see the default values (but do not edit the `defaults.cfg` file).
3. Edit the `/etc/ensconce/logging.cfg` to setup logging for your application.  Syslog is the recommended (and default) destination,
   but any python logging setup will work.

### Setup and Initialize the Database

#### PostgreSQL Setup

1. Create the database user.  You may wish to do this differently depending on your needs. See the `postgresql docs <http://www.postgresql.org/docs/9.1/static/app-createuser.html>`_ 
   for details.
   ```
   root@localhost# su - postgres
   postgres@localhost$ createuser -P ensconce
   Enter password for new role: <enter-your-password>
   ```
2. Create the database, ensuring it is owned by the user you created in step 1.  See the `postgresql docs <http://www.postgresql.org/docs/9.1/static/app-createdb.html>`_ for command details.
   ```
   postgres@localhost$ createdb -O ensconce -E UTF8 ensconce
   ```
3. Adjust your `pg_hba.conf` file to provide access for the new user.   Again there are lots of ways to do this, some more secure than others.  
   See the `postgresql docs <>`_ for details.  A simple example might be to add the following line to the top of the access control lines: 
   ```
   # TYPE  DATABASE   USER    ADDRESS  METHOD
   local   ensconce   ensconce         md5
   ```

### Initialize the Crypto

Before you can begin using the system (or start the web application), you will need to setup the encryption.  Ensconce ships with a commandline utility suite to help out here.

.. code-block:: none
    shell# /opt/ensconce/env/bin/paver -f /opt/ensconce/pavement.py init_crypto

Follow the interactive prompts.  Be very careful when entering the passphrase to not include whitespace etc.
Take advantage of the fact that the interactive prompts will print out the MD5 to double-check that everything is correct.  
**Getting this wrong could have serious data-loss consequences.**

### Start the Server

Starting the application is a matter of starting up the web app and the Apache reverse proxy.

.. code-block:: none
    shell# service ensconce start
    shell# service httpd start

**Once the application is started, you must visit it in your web browser to initialize the crypto engine with the passphrase you specified above (in the Initializing the Crypto step).**
