# NOTE: On CentOS 5.x you must have the buildsys-macros package installed in order
# for these conditionals to work correctly.
%if 0%{?rhel}
%if 0%{?el5}
# Define a new basename for python (also is assumed to be prefix for the python packages)
%define __python_pkgname python26
%define __python_exe python2.6
# Override the global %{__python} macro to point to our own python version
%define __python %{_bindir}/%{__python_exe}
# Specify the distribute package to use
%define setuptools_package python26-distribute
%else
# We are assuming EL6 (<EL5 is not supported)
%define __python_exe python
%define __python_pkgname python
%define setuptools_package python-setuptools
%endif
%else
# We are assuming fedora
%define __python_exe python
%define __python_pkgname python
%define setuptools_package python-setuptools
%endif


# This is the "package name" that we use in naming the /etc, /var/run, /var/log, subdirs.
%define PACKAGE ensconce

# This is the directory where we will install a Python virtual environment.
%define venvdir /opt/%{PACKAGE}/env

# This is the top-level directory for the application.  (It matches the directory
# of the virtual environment in this case.)
%define packagedir /opt/%{PACKAGE}

# This is the directory (in /etc/) where we will keep configuration files.
%define configdir %{_sysconfdir}/ensconce

# some systems dont have initrddir defined -- it seems that CentOS may be one of them (?)
%{?_initrddir:%define _initrddir /etc/rc.d/init.d}

# The directory where apache keeps its config files
%define apacheconfigdir %{_sysconfdir}/httpd/conf.d

# We don't want RH helpfully recompiling our pyc files (potentially with the wrong version of python)
%define __os_install_post %{nil}

### Abstract ###

Name:           ensconce
Version:        %{version}
Release:        %{release}
Epoch:          %{epoch}
Summary:        Ensconce Password Manager
Group:          Applications/System

### Requirements ###

# It is critical to disable the automagical requirements gathering!  Without this
# rpmbuild will look at all the binary files we're bundling (like python) and add these
# as requirements.  (This breaks things.)
AutoReqProv:		0

# These are the requirements for installing the RPM.
Requires:	      %{__python_pkgname} >= 2.6
Requires:			  syslog, httpd, mod_ssl, gnupg, openldap

### Source ###

License:        BSD

# This needs to match the actual file that will be dropped in
Source:         %{name}-%{version}.tar.gz
Source1:        ensconce.init
Source2:        settings.cfg
Source3:        logging.cfg
Source4:        alembic.ini
Source5:        defaults.cfg
Source6:        ensconce-vhost.conf

### Build Configuration ###

# This is the conventional uniquely named build-root that Fedora recommends.
BuildRoot:        %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

BuildRequires:    %{__python_pkgname}-devel, %{setuptools_package}, %{__python_pkgname}-virtualenv
BuildRequires:    gcc, openldap-devel, postgresql-devel, mysql-devel

%description
Ensconce is a web-based password manager that stores passwords encrypted in PostgreSQL or MySQL(InnoDB) databases.

# -------------------------------------------------------------------
# Preparation
# -------------------------------------------------------------------
# The %setup macro is basically a "tar zxvf" shortcut; this is convention for RPMs
#
%prep
%setup -q

# -------------------------------------------------------------------
# Build
# -------------------------------------------------------------------
# The build step actually builds the project; this is a little less relevant for Python, though
# we'll skip the build in the %%install section (by passing --skip-build to python setup.py install)
#
%build

# First move the "public" dir out to top-level so it's not included in build
# This is so that we can move it later to a custom location and not end
# up with two copies.
# mv static .

%{__cp} %{SOURCE1} .
%{__cp} %{SOURCE2} .
%{__cp} %{SOURCE3} .
%{__cp} %{SOURCE6} .

# We do this with the virtualenv python now.
#%{__python} setup.py build

# -------------------------------------------------------------------
# Install
# -------------------------------------------------------------------
# This %%install scriptlet is the code that installs the build package into the temporary location.  This is NOT code that
# runs when installing the RPM on a target system; this is only relevant for the build process.
#
%install
%{__rm} -rf %{buildroot}

# Create all the needed directories:
%{__mkdir} -p %{buildroot}%{packagedir}
# %{__mkdir} -p %{buildroot}%{_sysconfdir}/cron.hourly
%{__mkdir} -p %{buildroot}%{configdir}
%{__mkdir} -p %{buildroot}%{_initrddir}
%{__mkdir} -p %{buildroot}%{_localstatedir}/lib/%{PACKAGE}/backups
%{__mkdir} -p %{buildroot}%{_localstatedir}/log/%{PACKAGE}
%{__mkdir} -p %{buildroot}%{_localstatedir}/tmp/%{PACKAGE}/sessions
%{__mkdir} -p %{buildroot}%{_localstatedir}/tmp/%{PACKAGE}/egg-cache

touch %{buildroot}%{_localstatedir}/log/%{PACKAGE}/application.log
touch %{buildroot}%{_localstatedir}/log/%{PACKAGE}/startup.log

%{__mkdir} -p %{buildroot}%{_localstatedir}/run/%{PACKAGE}

# Install our "static" dir into the top-level of the package dir.
%{__mv} static %{buildroot}%{packagedir}

# Install our migrations dir into the top-level of the package dir.
%{__mv} migrations %{buildroot}%{packagedir}

# Move the files into the appropriat /var/lib/ directory.
# mv data/files %{buildroot}%{_localstatedir}/lib/%{PACKAGE}/

# Now move the rest of the data dir to our pkg directory.
# %{__mv} data %{buildroot}%{packagedir}

# Copy in the pavement.py since we use this for utility scripts (like migrations) later.
%{__mv} pavement.py %{buildroot}%{packagedir}

# Create a virtual environment for this application
%{__python} -m virtualenv --distribute --no-site-packages %{buildroot}%{venvdir}


# Remove the lib64 symlink that was added by virtualenv and replace with a non-absolute-path symlink
# (This only applies to builds on x86_64 arch.)

if [ -h "%{buildroot}%{venvdir}/lib64" ]
then
    rm %{buildroot}%{venvdir}/lib64
    ln -s lib %{buildroot}%{venvdir}/lib64
fi

# Define a new macro to refer to our virtualenv python
%define __venv_python %{buildroot}%{venvdir}/bin/%{__python_exe}

# This was moved from the %%build phase, since it appears to work better (or "at all")
# with the venv python.  We probably don't need to have this be a separate command, anymore.
%{__venv_python} setup.py build

# Use our newly installed virtualenv python to install the package (and dependencies)
# Note: this part will probably require that the user has an HTTP connection (to fetch deps).
%{__venv_python} setup.py install --skip-build

# Fix the incorrect absolute path that will exist in files in venv bin directory.
# (virtualenv sticks absolute paths in shebang headers and in the contents of the activate_this.py)
for file in %{buildroot}%{venvdir}/bin/*
do
	if [ "`basename $file`" != "python" ] && [ "`basename $file`" != "%{__python}" ]
	then
		%{__sed} -i -e "s|%{buildroot}%{venvdir}|%{venvdir}|" $file
	fi
done

# Do the same thing in the EGG-INFO/scripts dirs.
for file in %{buildroot}%{venvdir}/lib/python*/site-packages/*/EGG-INFO/scripts/*
do
	%{__sed} -i -e "s|%{buildroot}%{venvdir}|%{venvdir}|" $file
done

# Do the same for any .pth files
for file in %{buildroot}%{venvdir}/lib/python*/site-packages/*.pth
do
    %{__sed} -i -e "s|%{buildroot}%{venvdir}|%{venvdir}|" $file 
done

# And do the same thing for any RECORD metadata files.
for file in %{buildroot}%{venvdir}/lib/python*/site-packages/*/RECORD
do
	%{__sed} -i -e "s|%{buildroot}%{venvdir}|%{venvdir}|" $file
done

# Recompile the pyc files, using our final %{venvdir} as the root (rather than the current build dir)
%{__venv_python} -c 'from compileall import *; compile_dir("%{buildroot}%{venvdir}", maxlevels=20, ddir="%{venvdir}", force=True)'

# Remove all installed dependency_links.txt files, since these may contain internal URLs (and aren't needed in the RPM anyway)
find %{buildroot}%{venvdir} -name "dependency_links.txt" -exec rm {} \;

# Install non-Python files into the right places
%{__install} %{SOURCE1} %{buildroot}%{_initrddir}/ensconce
%{__install} %{SOURCE2} %{buildroot}%{configdir}
%{__install} %{SOURCE3} %{buildroot}%{configdir}
%{__install} %{SOURCE4} %{buildroot}%{configdir}
%{__install} %{SOURCE5} %{buildroot}%{packagedir}

# Install the Apache config file(s)
%{__install} -d -m 755 %{buildroot}%{apacheconfigdir}
%{__install} %{SOURCE6} %{buildroot}%{apacheconfigdir}

%{__install} -d -m 755 %{buildroot}%{configdir}/ssl
%{__install} resources/ssl/server-cert.pem %{buildroot}%{configdir}/ssl
%{__install} resources/ssl/server-key.pem %{buildroot}%{configdir}/ssl

# -------------------------------------------------------------------
# Cleanup Routine
# -------------------------------------------------------------------
%clean
rm -rf %{buildroot}

# -------------------------------------------------------------------
# The files that should be included in RPM
# -------------------------------------------------------------------
#
# The %files section needs to list all of the files, with their final
# resulting absolute paths (not the path to the temporary location where
# they were put by %%install).

%files
# By default chown everything root:root
%defattr(-,root,root,-)

# the /etc/ensconce/*.cfg files are config files & should not be overwritten
%config(noreplace) %{configdir}/settings.cfg
%config(noreplace) %{configdir}/logging.cfg
# we'll allow this one to get replaced (and have a .rpmsave made), since it's
# just for the alembic utility script.
%config %{configdir}/alembic.ini

# Our default/example certs
%config(noreplace) %attr(0600,root,root) %{configdir}/ssl/server-key.pem
%config(noreplace) %attr(0600,root,root) %{configdir}/ssl/server-cert.pem

# Apache configs
%config(noreplace) %attr(0644,root,root) %{apacheconfigdir}/ensconce-vhost.conf

# Include the entire contents of %{packagedir}
%{packagedir}/

# Add the init.d script
%attr(755,root,root) %{_initrddir}/ensconce

# Add the log directory (only dir, no contents) with correct ownership
%attr(0774,ensconce,ensconce) %dir %{_localstatedir}/log/%{PACKAGE}
%ghost %{_localstatedir}/log/%{PACKAGE}/application.log
%ghost %{_localstatedir}/log/%{PACKAGE}/startup.log

# Add the tmp dirs
%attr(0700,ensconce,ensconce) %dir %{_localstatedir}/tmp/%{PACKAGE}
%attr(0700,ensconce,ensconce) %dir %{_localstatedir}/tmp/%{PACKAGE}/sessions
%attr(0700,ensconce,ensconce) %dir %{_localstatedir}/tmp/%{PACKAGE}/egg-cache

# Add the storage dir
%attr(0700,ensconce,ensconce) %dir %{_localstatedir}/lib/%{PACKAGE}
%attr(0700,ensconce,ensconce) %dir %{_localstatedir}/lib/%{PACKAGE}/backups

# Add the pid/lock directory (only dir, no contents) with correct ownership
%attr(0700,ensconce,ensconce) %dir %{_localstatedir}/run/%{PACKAGE}

# -------------------------------------------------------------------
# RPM pre/post install scripts
# -------------------------------------------------------------------
#
# See http://fedoraproject.org/wiki/Packaging/ScriptletSnippets for
# some good documentation on how these work.
#
# Excerpt from docs:
# The scriptlets also take an argument, passed into them by the
# controlling rpmbuild process. This argument, accessed via $1 is the
# number of packages of this name which will be left on the system when
# the action completes, except for %pretrans and %posttrans which are
# always run with $1 as 0 (%pretrans and %posttrans are available in
# rpm 4.4 and later). So for the common case of install, upgrade, and
# uninstall we have:
#	            install 	upgrade 	uninstall
#   %pretrans 	$1 == 0 	$1 == 0 	(N/A)
#   %pre 	    $1 == 1 	$1 == 2 	(N/A)
#   %post 	    $1 == 1 	$1 == 2 	(N/A)
#   %preun 	    (N/A) 	    $1 == 1 	$1 == 0
#   %postun 	(N/A) 	    $1 == 1 	$1 == 0
#   %posttrans 	$1 == 0 	$1 == 0 	(N/A)
#

# Before install:
%pre
%{_sbindir}/groupadd -r -f ensconce
grep \^ensconce /etc/passwd >/dev/null
if [ $? -ne 0 ]; then
  %{_sbindir}/useradd -d %{configdir} -g ensconce -M -r ensconce
fi

# Before uninstall (or upgrade):
%preun
# only do this if it is not an upgrade
if [ $1 -eq 0 ]
then
   /sbin/chkconfig --del ensconce
   [ -f %{_initrddir}/ensconce ] && %{_initrddir}/ensconce stop
fi

# After install (or upgrade):
%post
/sbin/chkconfig --add ensconce

# Ensure the log files are owned by ensconce:ensconce
touch /var/log/ensconce/application.log
/bin/chown ensconce:ensconce /var/log/ensconce/application.log

touch /var/log/ensconce/startup.log
/bin/chown ensconce:ensconce /var/log/ensconce/startup.log

# Perform model upgrade and restart server if this is an upgrade
# (This is probably not a good idea to do in the post script.)
#
#if [ $1 -gt 1 ]
#then
#   # %{venvdir}/bin/paver -f %{packagedir}/pavement.py upgrade_db
#   [ -f %{_initrddir}/ensconce ] && %{_initrddir}/ensconce restart
#fi


%changelog
* Tue May 20 2014 Hans Lellelid <hans@xmpl.org> 1.4.0-1
- Initial public release.
