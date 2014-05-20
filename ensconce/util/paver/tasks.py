"""
Paver tasks common to the WT group.

These tasks are available via the wt_paver_tasks egg

WT projects should have a build_requires dependency on wt_paver_tasks
Then the pavement.py files for the projects can import wt_paver_tasks, and reuse these tasks

"""
import time
import os
import re
import shutil
import warnings
from ConfigParser import SafeConfigParser, NoOptionError

import pkg_resources

from paver.path import path
from paver.tasks import help, BuildFailure
from paver.easy import task, needs, cmdopts, sh, info, debug, error
from paver.tasks import BuildFailure

__all__ = ['help', 'clean', 'develop', 'test', 'tar', 'rpm', 'copy_rpm_sources', 
           'configure', 'validate_versions', 'init_build_env']

DEFAULTS_CONFIG_FILE_NAME = 'defaults.config'
CONFIG_FILE_NAME = 'build.config'

CWD = None
DIST_DIR = None
BUILD_DIR = None
BUILD_WORK_DIR = None
RPM_TOPDIR = None
OUTPUT_DIR = None
PKG_NAME = None
PKG_NAME_FULL = None
RPM_RESOURCES_DIR = None
SPEC_FILE = None

VERSION = None
RELEASE = None
EPOCH = None

TESTING = None
STRICT_BUILD = None

config = SafeConfigParser()

def raise_build_error(message, exc_type):
    """ Raises an exception or issues a warning, depending on whether "strict" was set to true or false. """
    if STRICT_BUILD:
        raise exc_type(message)
    else:
        warnings.warn(message, exc_type)

class UnconventionalBuild(Warning):
    """
    Warning raised when a project isn't following the WT build conventions.
    """
    pass

class NoRpmPackaging(Warning):
    """
    Warning raised when a project has no RPM packaging (say for an egg-only packaging)
    """
    pass
        
@task
@cmdopts([
    ('nonstrict', '-S', 'Whether to issue warnings instead of raising exception on build deviations.'),
    ('testing', 't', 'Whether this is a testing (vs. stable) package (will include epoch for RPM, etc.)')
    ])
def configure(options):
    """
    Reads and parses configuration options, setting global vars.
    """
    global CWD, BUILD_DIR, DIST_DIR, OUTPUT_DIR, RPM_TOPDIR, BUILD_WORK_DIR, SPEC_FILE
    global RPM_RESOURCES_DIR
    global PKG_NAME, PKG_NAME_FULL, CONFIG_FILE_NAME, STRICT_BUILD, TESTING
    global EPOCH, VERSION, RELEASE
    
    # Some globals that need to be available
    config.add_section('build')
    config.add_section('site')
    
    CWD = path(os.getcwd())
    
    config.set('build', 'cwd', CWD)
    config.set('build', 'uid', str(os.getuid()))
    config.set('build', 'user', os.getenv('USER'))
    
    # Read in the default config file.
    fp = pkg_resources.resource_stream('ensconce.util.paver', 'defaults.config') # Intentionally not using the DEFAULTS_CONFIG_FILE_NAME var here.
    try:
        config.readfp(fp)
    finally:
        fp.close()
        
    # Read in config from the CWD
    config.read([str(CWD / path(DEFAULTS_CONFIG_FILE_NAME)), str(CWD / path(CONFIG_FILE_NAME))])
    
    BUILD_DIR = path(config.get('build', 'build_dir'))
    DIST_DIR = path(config.get('build', 'dist_dir'))
    RPM_TOPDIR = path(config.get('build', 'rpm_topdir'))
    
    RPM_RESOURCES_DIR = path(config.get('build', 'rpm_resources_dir'))
    SPEC_FILE = path(config.get('build', 'spec_file'))
    
    PKG_NAME = config.get('build', 'package')
    if not PKG_NAME:
        raise BuildFailure("You must define 'package' option in config with name of your package.")
        
    distribution = pkg_resources.get_distribution(PKG_NAME) # will throw exc if not found
    
    VERSION = distribution.version
    RELEASE = config.get('build', 'release')
        
    PKG_NAME_FULL = '%s-%s' % (PKG_NAME, VERSION)
    
    BUILD_WORK_DIR = BUILD_DIR / path(PKG_NAME_FULL)
        
    # Set EPOCH to current time (unix epoch) if "testing" was specified; else 0
    try:
        TESTING = options.configure.testing
    except AttributeError:
        TESTING = False
    
    if TESTING:
        EPOCH = int(time.time())
    else:
        EPOCH = 0
    
    try:
        STRICT_BUILD = (not options.configure.nonstrict)
    except AttributeError:
        STRICT_BUILD = (config.getboolean('build', 'strict'))
    
    # For now just always assume we want our final products in DIST_DIR
    OUTPUT_DIR = DIST_DIR

@task
def validate_versions():
    validate_version(VERSION, testing=bool(TESTING))
    validate_release(RELEASE)


@task
@needs(['configure'])
def clean():
    """Clean derived files.

    Basic task for cleaning up after a build.
    WT Build Conventions Addressed: (#1, #2).
    """
    BUILD_DIR.rmtree()
    DIST_DIR.rmtree()

@task
@needs(['configure', 'clean'])
def init_build_env():
    """ Cleans and initializes the build environment. """
    BUILD_DIR.rmtree()
    if not BUILD_DIR.exists():
        BUILD_DIR.makedirs()
    if not BUILD_WORK_DIR.exists():
        BUILD_WORK_DIR.makedirs()
    # FIXME - maybe a full tree not needed?
    for subdir in ('RPMS', 'SPECS', 'SOURCES', 'BUILD', 'SRPMS'):
        (RPM_TOPDIR / path(subdir)).makedirs()
        
    DIST_DIR.rmtree()
    if not DIST_DIR.exists():
        DIST_DIR.makedirs()
        
@task
def develop():
    """
    Call "python setup_py develop".
    """
    sh("python setup.py develop")

@task
def test():
    """ Run project tests.

    This task will be called before the rpm task, to ensure all the project's unit tests
    pass before the RPM is built.
    """
    sh('python setup.py test')

@task
@needs(['init_build_env', 'validate_versions'])
def tar():
    """ Create a tar.gz package. """
    sh('python setup.py sdist')

@task
@needs(['tar'])
def copy_rpm_sources():
    """ Copy the tgz, any additional sources, and SPEC file into RPM tree. """    
    # Copy the tgz file that we built.  We are assuming a standard name here.
    (path(DIST_DIR) / path('%s.tar.gz' % PKG_NAME_FULL)).copy((RPM_TOPDIR / path('SOURCES')))
    # Any other files in the rpm dir we'll put in there too.
    for fn in RPM_RESOURCES_DIR.walkfiles('*'):
        if not fn.endswith('.spec'): # Don't also copy the SPEC file into sources
            path(fn).copy((RPM_TOPDIR / path('SOURCES')))
    # Finally, copy the SPEC out into the SPECS dir
    (path(SPEC_FILE)).copy((RPM_TOPDIR / path('SPECS')))
    
@task
@needs(['copy_rpm_sources'])
def rpm():
    """ Create an RPM. """
    build_rpm(SPEC_FILE)


def build_rpm(specfile, vars=None):
    """
    Builds the RPM with given specfile basename.
    @param specfile: The basename of specfile (expects to be in SPECS dir).
    @param vars: dict of additional variables to define for the rpm build.
    """
    cmd = "rpmbuild --define '_topdir %(topdir)s'" \
          + " --define 'version %(version)s'" \
          + " --define 'epoch %(epoch)d'" \
          + " --define 'release %(release)s'"
    if vars:
        for (k,v) in vars.items():
            cmd += " --define '%s %s'" % (k,v)
            
    cmd += " -bb %(specfile)s 2>&1"
              
    sh(cmd % {'epoch': EPOCH, 
              'version': VERSION, 
              'release': RELEASE,
              'topdir': RPM_TOPDIR,
              'specfile': RPM_TOPDIR / path('SPECS') / path(specfile)}, capture=False)
    
    info("***************************************************************")
    info("Your RPM(s) have been built.")
    if OUTPUT_DIR:
        for fn in (RPM_TOPDIR / path('RPMS')).walkfiles('*.rpm'):
            path(fn).copy(OUTPUT_DIR)        
            info("Copied (binary) RPM %s to %s" % (fn, OUTPUT_DIR))
        for fn in (RPM_TOPDIR / path('SRPMS')).walkfiles('*.rpm'):
            path(fn).copy(OUTPUT_DIR)        
            info("Copied (source) RPM %s to %s" % (fn, OUTPUT_DIR))
    else:
        info("Binary RPMs here: %s" % (RPM_TOPDIR / path('RPMS')))
        info("Source RPMs here: %s" % (RPM_TOPDIR / path('SRPMS')))
    info("***************************************************************")

def validate_version(version, testing=False):
    """
    Validates the version as a X.X.X version for stable builds and
    X.X version for testing builds.
    """
    
    version_parts = version.split('.')
    
    if testing:
        expected_versions = ('major', 'minor')
        if len(version_parts) != 2:
            raise_build_error("Testing packages should have version in major.minor format", UnconventionalBuild)
    else:
        expected_versions = ('major', 'minor', 'bugfix')
        if len(version_parts) != 3:
            raise_build_error("Stable packages should have version in major.minor.bugfix format", UnconventionalBuild)
    
    for (i,type) in enumerate(expected_versions):
        try:
            if type == 'bugfix':
                # special handling of the final part of version; it must start
                # with a number, but can have qualifiers.
                m = re.match(r'^\d+(rc|a|b|c|dev)?\d*$', version_parts[i])
                if not m:
                    raise_build_error("%s portion of version does not match expectations: %s" % (type, version), UnconventionalBuild)
            else:
                int(version_parts[i])
        except IndexError:
            pass
        except ValueError:
            raise_build_error("%s portion of version is not an integer: %s" % (type, version), UnconventionalBuild)

def validate_release(release):
    try:
        int(release)
    except ValueError:
        raise_build_error("release is not an integer: %s" % release, UnconventionalBuild)
