# ATTENTION! File managed by Puppet. Changes will be overwritten.

"""
SAF concept
~~~~~~~~~~~~~~~~~~~~~

SAF is a devops-driven concept for operating and staging of applications

Example usage:

   >>> import saf
   >>> saf.init('/path/to/saf.conf')
   >>> r = saf.app.ls('my*')
   >>> print(r.rc)
   0
   >>> print(r.stdout)
   myapp1
   myapp2
   >>> print(r.json)
   {'rc':'True', 'apps':['myapp1','myapp2']}


:copyright: (c) 2017 Stefan Steinert
:license: Copyright (c) T-Systems Schweiz

"""
import sys

__title__ = 'saf'
__version__ = '2.2.2pre'
__txversion__ = '1'
__author__ = 'Stefan Steinert'

import os

import logging

logger = logging.getLogger(__name__)

# suppress urllib3 https warnings
try:
    import urllib3
except ImportError:
    from packages.requests.packages import urllib3

urllib3.disable_warnings()

import warnings
warnings.simplefilter('ignore')

# http://stackoverflow.com/questions/11029717/how-do-i-disable-log-messages-from-the-requests-library#11029841
logging.getLogger("requests").setLevel(logging.WARNING)

# This hack became necessary because I was unable to "subpackage" psutil inside saf. Doing
# "import saf.packages.psutil" resulted in:
#    Traceback (most recent call last):
#    File "/app/saf/lib/saf/packages/psutil/__init__.py", line 1610, in <module>
#    _last_cpu_times = cpu_times()
#    File "/app/saf/lib/saf/packages/psutil/__init__.py", line 1604, in cpu_times
#    return _psplatform.cpu_times()
#    File "/app/saf/lib/saf/packages/psutil/_pslinux.py", line 552, in cpu_times
#    procfs_path = get_procfs_path()
#    File "/app/saf/lib/saf/packages/psutil/_pslinux.py", line 214, in get_procfs_path
#    return sys.modules['psutil'].PROCFS_PATH
#    KeyError: 'psutil'
# Also add lib/saf/packages to your IDE source path for symbol lookups
sys.path.append(
    os.path.normpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'packages')))

import saf.app, saf.repo, saf.tx
from . import safutils
from saf.exceptions import *

base_path = os.path.normpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', '..'))

# default time format used for output
time_format = '%Y-%m-%d %H:%M:%S'

# The main config dictionary (built from configfile, saf.conf by default)
config = None

# Temp directory for overlaying and other stuff
temp_dir = None


@safutils.method_trace
def init(conf_file=None):
    # https://stackoverflow.com/questions/1977362/how-to-create-module-wide-variables-in-python#1978076
    global config, temp_dir
    if config is not None:
        return
    else:
        if conf_file is None:
            if os.getenv('SAF_CONFIG_FILE') is not None:
                logger.debug(
                    'SAF_CONFIG_FILE set, auto-init from %s' % os.getenv('SAF_CONFIG_FILE'))
                conf_file = os.getenv('SAF_CONFIG_FILE')
            else:
                raise SafInitException(
                    'Could not determine config file. Pass it as parameter or set SAF_CONFIG_FILE in env.')

        import ConfigParser
        # default values could be passed to constructor
        config = ConfigParser.SafeConfigParser()
        try:
            open(conf_file)
        except IOError as e:
            raise SafInitException('Cannot open config file %s: %s' % (conf_file, e))
        config.read(conf_file)
        logger.debug('config._sections():%s' % config._sections)
        config_dict = {}
        for section in config.sections():
            for (name, value) in config.items(section):
                config_dict[name] = value
        logger.debug('config_dict:%s' % config_dict)
        config = config_dict

        for mand_param in ['basedir']:
            if mand_param not in config.keys():
                raise SafConfigException(
                    'Mandatory parameter "%s" missing in %s' % (mand_param, conf_file))

        if not os.path.exists(config['basedir']):
            raise SafInitException('SAF basedir "%s" missing' % config['basedir'])

        for saf_dir in ['apps', 'transactions', 'var', os.path.join('var', 'temp')]:
            component_path = os.path.join(config['basedir'], saf_dir)
            if not os.path.isdir(component_path):
                try:
                    logger.info('creating %s' % component_path)
                    os.makedirs(component_path, mode=0o755)
                except OSError as e:
                    raise SafInitException(e)
        temp_dir = os.path.join(config['basedir'], 'var', 'temp')
