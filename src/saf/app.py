# ATTENTION! File managed by Puppet. Changes will be overwritten.

import getpass
import os
import subprocess

import re
import shlex
import socket
import sre_constants
import threading

import time

import resource

import datetime

import saf
import saf.tx
import saf.safutils

from . import safutils

from saf.exceptions import *

import requests

import logging

logger = logging.getLogger(__name__)


try:
    import psutil
except ImportError as e:
    raise SafExecutionException(e)


class Application(safutils.IKnowhow):
    #TODO use python @property annotation for all property-like features (e.g. pids, is_running...)
    @safutils.method_trace
    def _run_app(self):
        """ run a SAF app """

        # http://stackoverflow.com/questions/1191374/using-module-subprocess-with-timeout#4825933
        class AppRunner(object):

            @safutils.method_trace
            def __init__(self, app):
                self.app = app
                self.pidfile = app.pidfile()
                self.timeout = app.start_timeout()
                self.rc = 0

            @safutils.method_trace
            def do_command(self):
                @safutils.method_trace
                def run_the_app():
                    logger.debug('self.app:%s' % self.app)

                    # http://codereview.stackexchange.com/questions/6567/redirecting-subprocesses-output-stdout-and-stderr-to-the-logging-module
                    # nice idea but impossible here because the log consumer thread lifetime cannot
                    # exceed interpreter lifetime (which is required because the app keeps running)
                    # app_handler = logging.handlers.RotatingFileHandler(os.path.join(app_path, 'log/startup.log'), maxBytes=1024, backupCount=3)
                    # app_logger = logging.getLogger('app')
                    # app_logger.addHandler(app_handler)
                    # logWrap = LoggerWrapper(app_logger, logging.INFO)
                    # self.rc = subprocess.call(self.cmd, cwd=self.path, stdout=logWrap, stderr=logWrap)

                    out_file = open(os.path.join(self.app.basedir, 'log/startup.log'), 'a')
                    out_file.write(
                        '----- %s ----- application start -----\n' % datetime.datetime.now().strftime(
                            saf.time_format))

                    self.rc = subprocess.call(self.app.launch_command(), cwd=self.app.basedir,
                                              stdout=out_file, stderr=out_file)

                    logger.debug('app finished rc:%s' % self.rc)

                app_thread = threading.Thread(target=run_the_app)
                app_thread.daemon = True
                app_thread.start()

                if self.pidfile is None:
                    logger.debug('waiting for app_thread')
                    app_thread.join(self.timeout)
                    if not app_thread.is_alive():
                        if self.rc == 0:
                            logger.warning(
                                'application exited with rc=0. This is not the expected behaviour. If your application daemonizes then please change its app.conf to use launcher.daemon.pidfile instead of process.regex')
                        else:
                            raise SafExecutionException(
                                'application exited with rc=%s. See %s for details' % (
                                    self.rc, os.path.join(self.app.basedir, 'log/startup.log')))
                else:
                    app_thread.join(5)
                    if not app_thread.is_alive():
                        logger.debug('daemon dead')
                        if self.rc != 0:
                            raise SafExecutionException(
                                'daemon exited with rc=%s. See %s for details' % (
                                    self.rc, os.path.join(self.app.basedir, 'log/startup.log')))
                    pidfile_exists = False
                    now = time.time()
                    while time.time() - now < self.timeout:
                        if os.path.isfile(self.pidfile):
                            pidfile_exists = True
                            break
                        time.sleep(0.3)
                    if pidfile_exists:
                        try:
                            self.app.is_running()
                        except Exception as e:
                            raise e
                    else:
                        raise SafExecutionException(
                            'daemon did not create a pidfile %s in time' % self.pidfile)

        AppRunner(self).do_command()

    @safutils.method_trace
    def __init__(self, name):
        self.basedir = os.path.join(saf.config['basedir'], 'apps', name)
        self.name = name

        self._config = safutils.parse_kv_file('%s.conf' % self.basedir)

        self._knowhow = dict([(key, self._config[key]) for key in self._config.keys() if
                              key.startswith('knowhow.app')])
        # use nicer dict comprehension syntax in py2.7+ instead of above dict()
        # self._knowhow = {key: self._config[key] for key in self._config.keys() if key.startswith('knowhow.app'}
        logger.debug('self.knowhow:%s' % self._knowhow)

        app_meta_file = '%s.meta' % self.basedir
        logger.debug('app_meta_file:%s' % app_meta_file)
        try:
            self.meta = safutils.parse_kv_file(app_meta_file)
            # "pre-versioning saf2" uses partly different meta prop names. Remove this as soon
            # legacy saf (bash code) is gone
            if 'version' in self.meta.keys():
                self.meta['app_version'] = self.meta['version']
                del self.meta['version']
                self.meta['app_name'] = self.meta['application']
                del self.meta['application']
        except SafConfigException as e:
            logger.warn('could not get metadata for app %s: %s' % (self.name, e))
            self.meta = {}

    @safutils.method_trace
    def start(self, iknow):
        if self.is_running():
            raise SafExecutionException('App %s already running' % self.name)

        if 'force_user' in saf.config.keys():
            if getpass.getuser() != saf.config['force_user']:
                raise SafExecutionException(
                    'Only user %s is allowed to start an application.' % saf.config['force_user'])

        safutils.assert_knowhow(self, 'knowhow.app.start', iknow)

        if self.maxfiles() is not None:
            current_nofile = resource.getrlimit(resource.RLIMIT_NOFILE)
            if current_nofile[0] != self.maxfiles():
                logger.debug(
                    'setting nofile(soft) from %s to %s' % (current_nofile[0], self.maxfiles()))
                resource.setrlimit(resource.RLIMIT_NOFILE, (self.maxfiles(), current_nofile[1]))

        if self.maxprocs() is not None:
            current_noproc = resource.getrlimit(resource.RLIMIT_NPROC)
            if current_noproc[0] != self.maxprocs():
                logger.debug(
                    'setting noproc(soft) from %s to %s' % (current_noproc[0], self.maxprocs()))
                resource.setrlimit(resource.RLIMIT_NPROC, (self.maxprocs(), current_noproc[1]))

        for env_entry in self.env_entries():
            os.environ[env_entry[0]] = env_entry[1]

        try:
            if not os.path.exists(os.path.join(self.basedir, 'log')):
                os.makedirs(os.path.join(self.basedir, 'log'), mode=0o0755)
        except OSError as e:
            raise SafExecutionException('Cannot create application log directory: %s' % e)

        self._run_app()

    @safutils.method_trace
    def stop(self, iknow):
        @safutils.method_trace
        def on_terminate(proc):
            logger.debug('pid %s ended after SIGTERM' % proc.pid)

        @safutils.method_trace
        def on_kill(proc):
            logger.debug('pid %s ended after SIGKILL' % proc.pid)

        timeout = self.stop_timeout()

        if not self.is_running():
            raise SafExecutionException('%s not running' % self.name)

        safutils.assert_knowhow(self, 'knowhow.app.stop', iknow)

        proc_list = [psutil.Process(pid) for pid in self.pids()]
        for proc in proc_list:
            logger.debug('terminating pid %s, cmdline "%s"' % (proc.pid, proc.cmdline()))
            proc.terminate()
        gone, still_alive = psutil.wait_procs(proc_list, timeout=timeout, callback=on_terminate)
        logger.debug('gone (after SIGTERM) %s ...' % gone)
        logger.debug('still_alive (after SIGTERM) %s ...' % still_alive)
        if len(still_alive) > 0:
            for proc in still_alive:
                logger.warn('forcefully killing pid %s (cmdline "%s")' % (proc.pid, ' '.join(
                    proc.cmdline())))
                proc.kill()
            gone, still_alive = psutil.wait_procs(proc_list, timeout=timeout, callback=on_kill)
            logger.debug('gone (after SIGKILL) %s ...' % gone)
            logger.debug('still_alive (after SIGKILL) %s ...' % still_alive)
        if len(still_alive) > 0:
            pid_list = [str(proc.pid) for proc in still_alive]
            raise SafExecutionException(
                'Could not end %s (PID(s) %s)' % (self.name, ','.join(pid_list)))
        else:
            if self.daemonizes():
                if os.path.exists(self.pidfile()):
                    os.remove(self.pidfile())

    @safutils.method_trace
    def pids(self, recursive=True):
        procs = []
        if self.daemonizes():
            pidfile_name = self.pidfile()

            if os.path.isfile(pidfile_name):
                try:
                    pidfile = open(pidfile_name, 'r')
                    content = pidfile.read()
                    pidfile.close()
                    daemon_pid = int(content)
                    logger.debug('daemon_pid:%s' % daemon_pid)
                    try:
                        procs.append(psutil.Process(daemon_pid))
                        if recursive:
                            procs.extend(procs[0].children(recursive=True))
                    except psutil.NoSuchProcess as e:
                        logger.warn('Removing stale pidfile %s: %s' % (pidfile_name, e))
                        os.remove(pidfile_name)
                except IOError as e:
                    raise SafExecutionException('Could not open pidfile %s: %s' % (pidfile_name, e))
                except ValueError as e:
                    raise SafExecutionException(
                        'Could not interpret pidfile %s: %s' % (pidfile_name, e))
        else:
            if 'process.regex' not in self._config.keys():
                raise SafConfigException('process.regex not defined in application conf')

            try:
                pattern = re.compile(self._config['process.regex'])
            except sre_constants.error as e:
                raise SafConfigException(
                    'Invalid regular expression "%s": %s' % (self._config['process.regex'], e))
            master_procs = []
            for process in psutil.process_iter():
                process_info = process.as_dict(attrs=['pid', 'cmdline'])
                if process_info['cmdline'] is not None:
                    if re.search(pattern, ' '.join(process_info['cmdline'])):
                        master_procs.append(process)
            logger.debug('master_pids:%s' % [proc.pid for proc in master_procs])
            if recursive:
                for master_proc in master_procs:
                    procs.append(master_proc)
                    procs.extend(master_proc.children(recursive=True))
            else:
                procs = master_procs
        pids = sorted([proc.pid for proc in procs])
        logger.debug('pids:%s' % pids)
        return pids

    @safutils.method_trace
    def is_running(self):
        return len(self.pids()) > 0

    @safutils.method_trace
    def launch_command(self):
        command = []
        if 'launcher.file' not in self._config.keys():
            raise SafConfigException('launcher.file not defined in application conf')
        else:
            if self._config['launcher.file'][0] == '/' or '..' in self._config['launcher.file']:
                raise SafConfigException(
                    'launcher.file must be specified relative to application root dir. Found: %s' %
                    self._config['launcher.file'])

        file_name_abs = os.path.join(self.basedir, self._config['launcher.file'])
        perms = os.stat(file_name_abs).st_mode & 0o0777
        new_perms = perms | 0o0500
        if perms != new_perms:
            logger.debug('chmod %s: %o > %o' % (file_name_abs, perms, new_perms))
            os.chmod(file_name_abs, new_perms)

        command.append(os.path.join(self.basedir, self._config['launcher.file']))

        if 'launcher.args' in self._config.keys():
            command.extend(shlex.split(self._config['launcher.args']))
        logger.debug('command:%s' % command)
        return command

    @safutils.method_trace
    def maxfiles(self):
        result = None
        if 'process.maxfiles' in self._config.keys():
            try:
                maxfiles = int(self._config['process.maxfiles'])
                if maxfiles < 128 or maxfiles > 65536:
                    raise ValueError('allowable range is 128..65536')
                result = maxfiles
            except ValueError as e:
                raise SafConfigException('invalid process.maxfiles: %s' % e)
        logger.debug('result:%s' % result)
        return result

    @safutils.method_trace
    def maxprocs(self):
        result = None
        if 'process.maxprocs' in self._config.keys():
            try:
                maxprocs = int(self._config['process.maxprocs'])
                # 515190 is $(cat /proc/sys/kernel/threads-max) on Prod
                if maxprocs < 1024 or maxprocs > 515190:
                    raise ValueError('allowable range is 1024..515190')
                result = maxprocs
            except ValueError as e:
                raise SafConfigException('invalid process.maxprocs: %s' % e)
        logger.debug('result:%s' % result)
        return result

    @safutils.method_trace
    def env_entries(self):
        result = []
        for conf_key in self._config.keys():
            if conf_key.startswith('env.'):
                result.append((conf_key[4:], self._config[conf_key]))
        logger.debug('result:%s' % result)
        return result

    @safutils.method_trace
    def _timeout(self, param_name):
        result = 10
        if param_name in self._config.keys():
            try:
                val = int(self._config[param_name])
                if val < 5 or val > 180:
                    raise ValueError('allowable range is 5..180')
                result = val
            except ValueError as e:
                raise SafConfigException('invalid %s: %s' % (param_name, e))
        logger.debug('result:%s' % result)
        return result

    @safutils.method_trace
    def start_timeout(self):
        return self._timeout('timeout.start')

    @safutils.method_trace
    def stop_timeout(self):
        return self._timeout('timeout.stop')

    @safutils.method_trace
    def daemonizes(self):
        return self.pidfile() is not None

    @safutils.method_trace
    def pidfile(self):
        result = self._config.get('launcher.daemon.pidfile', None)

        if result is not None:
            if result[0] == '/':
                raise SafConfigException(
                    'launcher.daemon.pidfile must be specified relative to application root dir. Found: %s' % result)
            result = os.path.join(self.basedir, result)
        logger.debug('result:%s' % result)
        return result

    @safutils.method_trace
    def check_names(self):
        check_keys = [key for key in self._config.keys() if key.startswith('check.')]
        logger.debug('checks:%s' % check_keys)
        check_names = list()
        for check_key in check_keys:
            x, check_name, check_prop = check_key.split('.')
            if check_name not in check_names:
                check_names.append(check_name)
        logger.debug('check_names:%s' % check_names)
        return check_names

    @safutils.method_trace
    def check_url(self, check_name):
        if check_name not in self.check_names():
            raise SafConfigException('No check named "%s"' % check_name)

        if 'check.%s.method' % check_name in self._config.keys() and 'check.%s.port' % check_name in self._config.keys() and 'check.%s.path' % check_name in self._config.keys():

            method = self._config['check.%s.method' % check_name]
            port = self._config['check.%s.port' % check_name]
            path = self._config['check.%s.path' % check_name]

            if method != 'http' and method != 'https':
                raise SafConfigException(
                    'check.%s.method needs to be one of http or https' % check_name)
            try:
                if int(port) < 0 or int(port) > 65535:
                    raise SafConfigException(
                        'check.%s.port needs to be in range 0..65535' % check_name)
            except ValueError as e:
                raise SafConfigException('invalid check.%s.port: %s' % (check_name, e))
            if path[0] != '/':
                raise SafConfigException('check.%s.path needs to start with "/"' % check_name)
            result = '%s://%s:%s%s' % (method, socket.getfqdn(), port, path)
        elif 'check.%s.url' % check_name in self._config.keys():
            result = self._config['check.%s.url' % check_name]
        else:
            raise SafConfigException(
                'must specify either url or method/port/path (preferred) properties for check "%s"' % check_name)

        logger.debug('result:%s' % result)
        return result

    @safutils.method_trace
    def check_success_pattern(self, name):
        if name not in self.check_names():
            raise SafConfigException('No check named "%s"' % name)
        if 'check.%s.success' % name not in self._config.keys():
            raise SafConfigException('must specify "success" literal for check %s' % name)
        return self._config['check.%s.success' % name]

    @safutils.method_trace
    def knowhow(self):
        return safutils.ImmutableDict(self._knowhow)


@safutils.method_trace
def get_all_app_names():
    app_names = []
    apps_dir = os.path.join(saf.config['basedir'], 'apps')
    for dir_name in os.walk(apps_dir).next()[1]:
        if os.path.isfile(os.path.join(apps_dir, '%s.conf' % dir_name)):
            app_names.append(dir_name)
    app_names = sorted(app_names)
    logger.debug('app_names:%s' % app_names)
    return app_names


@safutils.method_trace
def _get_bootstart_app_names():
    app_names = get_all_app_names()
    apps_dir = os.path.join(saf.config['basedir'], 'apps')

    for app_name in app_names:
        app_config = safutils.parse_kv_file(os.path.join(apps_dir, '%s.conf' % app_name))
        if 'bootstart' in app_config.keys() and app_config['bootstart'].lower() == 'false':
            app_names.remove(app_name)
    logger.debug('bootstart_app_names:%s' % app_names)
    return app_names


@safutils.method_trace
def get_app_names(regex=None, all=False, bootstart=False):
    if all:
        apps = get_all_app_names()
    elif bootstart:
        apps = _get_bootstart_app_names()
    else:
        if regex is None:
            raise SafExecutionException('An app must be specified')
        apps = get_all_app_names()
        # http://stackoverflow.com/questions/3640359/regular-expressions-search-in-list#3640376
        import re
        try:
            pattern = re.compile('^%s$' % regex)
            apps = filter(pattern.match, apps)
        except sre_constants.error as e:
            raise SafExecutionException('Invalid regular expression: %s' % e)
        if len(apps) == 0:
            raise SafExecutionException('No app found matching %s' % regex)
    logger.debug('apps:%s' % apps)

    return apps


@safutils.method_trace
def ls(app_regex, all=False, bootstart=False, details=False, asjson=False):
    app_names = get_app_names(app_regex, all, bootstart)

    apps = dict()
    for app_name in app_names:
        apps[app_name] = Application(app_name)

    result = dict()
    for app_name in app_names:
        result[app_name] = dict()
        for app_property in ['app_version', 'deploy_time']:
            result[app_name][app_property] = apps[app_name].meta[app_property]
        result[app_name]['app_size'] = saf.safutils.directory_size(apps[app_name].basedir)

    if details:
        for app_name in app_names:
            for app_property in ['create_user', 'create_time', 'deploy_user', 'deploy_time']:
                result[app_name][app_property] = apps[app_name].meta[app_property]
            result[app_name]['app_size'] = saf.safutils.directory_size(apps[app_name].basedir)

    if asjson:
        logger.info(result)
    else:
        if details:
            app_list = [['NAME', 'VERSION', 'SIZE', 'CRT_USER', 'CRT_TIME', 'DPL_USER', 'DPL_TIME']]
            for app_name in result.keys():
                app_list.append(
                    [app_name, result[app_name]['app_version'], result[app_name]['app_size'],
                     result[app_name]['create_user'], result[app_name]['create_time'],
                     result[app_name]['deploy_user'], result[app_name]['deploy_time']])
        else:
            app_list = [['NAME', 'VERSION', 'SIZE', 'DEPLOY_TIME']]
            for app_name in result.keys():
                app_list.append(
                    [app_name, result[app_name]['app_version'], result[app_name]['app_size'],
                     result[app_name]['deploy_time']])
        formatted_lines = saf.safutils.align_columns(app_list)
        for line in formatted_lines:
            logger.info(line)

    return 0


@safutils.method_trace
def ps(app_regex, all=False):
    app_names = get_app_names(app_regex, all)

    result = [['PID', 'APP', 'START', '%CPU', 'RSS', '#FD', '#THR']]

    import time
    process_data = {}

    # sampling two times with small delay to get (more or less) current cpu_percent usage
    for p in psutil.process_iter():
        process_data[p.pid] = p.as_dict(
            ['create_time', 'cpu_percent', 'memory_info', 'num_fds', 'num_threads',
             'cpu_times'])
    time.sleep(0.5)
    for p in psutil.process_iter():
        process_data[p.pid] = p.as_dict(
            ['create_time', 'cpu_percent', 'memory_info', 'num_fds', 'num_threads',
             'cpu_times'])

    for app_name in app_names:
        app = Application(app_name)
        pids = app.pids()

        for pid in pids:
            result.append([pid,
                           app_name,
                           datetime.datetime.fromtimestamp(
                               process_data[pid]['create_time']).strftime(
                               saf.time_format),
                           process_data[pid]['cpu_percent'],
                           process_data[pid]['memory_info'].rss,
                           process_data[pid]['num_fds'], process_data[pid]['num_threads']])

    formatted_lines = saf.safutils.align_columns(result)
    for line in formatted_lines:
        logger.info(line)

    return 0


@safutils.method_trace
def pinfo(app_name, asjson=False):
    if app_name not in get_all_app_names():
        raise SafExecutionException('No such app: %s' % app_name)

    app = Application(app_name)
    if not app.is_running():
        raise SafExecutionException('Application %s is not running' % app_name)

    pids = app.pids()

    if asjson:
        result = dict()
        for pid in pids:
            pdict = psutil.Process(pid).as_dict()
            result[pid] = pdict
        logger.info(result)
    else:
        for pid in pids:
            logger.info('%s:' % pid)
            pdict = psutil.Process(pid).as_dict()
            safutils.prettyprint_dict(pdict)
            # logger.info(saf.packages.yaml.dump(pdict, default_flow_style=False, indent=4))

    return 0


@safutils.method_trace
def start(app_regex, all=False, bootstart=False, iknow=False):
    app_names = get_app_names(app_regex, all, bootstart)

    started = 0
    for app_name in app_names:
        app = Application(app_name)
        if app.is_running():
            logger.info('%s already running' % app_name)
        else:
            logger.info('Starting %s ...' % app_name)
            app.start(iknow)
            logger.info('OK')
        started += 1

    return len(app_names) - started


@safutils.method_trace
def stop(app_regex, all=False, bootstart=False, iknow=False):
    app_names = get_app_names(app_regex, all, bootstart)

    stopped = 0
    for app_name in app_names:
        app = Application(app_name)

        if not app.is_running():
            logger.info('%s already stopped' % app_name)
        else:
            logger.info('Stopping %s ...' % app_name)
            app.stop(iknow)
            logger.info('OK')
        stopped += 1

    return len(app_names) - stopped


@safutils.method_trace
def restart(app_regex, all=False, bootstart=False, iknow=False):
    app_names = get_app_names(app_regex, all, bootstart)

    rc = 0
    if len(app_names) == 0:
        raise SafExecutionException('No app found matching %s' % app_regex)

    for app_name in app_names:
        rc += stop(app_name, iknow=iknow)
        rc += start(app_name, iknow=iknow)

    return rc


@safutils.method_trace
def status(app_regex, all=False, bootstart=False, asjson=False):
    app_names = get_app_names(app_regex, all, bootstart)

    if asjson:
        result = dict()
        for app_name in app_names:
            app = Application(app_name)
            result[app_name] = app.pids()
        logger.info(result)
    else:
        for app_name in app_names:
            app = Application(app_name)

            if not app.is_running():
                logger.info("%s is stopped" % app_name)
            else:
                pids = app.pids()
                wording = 'PID'
                if len(pids) > 1:
                    wording += 's'
                # http://stackoverflow.com/questions/3590165/joining-a-list-that-has-integer-values-with-python#3590168
                logger.info(
                    "%s is running (%s %s)" % (app_name, wording, ','.join(str(x) for x in pids)))
    return 0


@safutils.method_trace
def tail(app_regex, all=False, bootstart=False):
    app_names = get_app_names(app_regex, all, bootstart)

    command = ['tail', '-n0', '-f']
    files = list()
    for app_name in app_names:
        app = Application(app_name)
        for root, dirnames, filenames in os.walk(os.path.join(app.basedir, 'log')):
            for filename in filenames:
                files.append(os.path.join(root, filename))
    if len(files) > 0:
        command.extend(files)
        saf.safutils.run_process(' '.join(command), log_output=False)
    else:
        logger.warning('No logfiles found')
    return 0


@safutils.method_trace
def check(app_regex, all=False, bootstart=False, details=False):
    app_names = get_app_names(app_regex, all, bootstart)

    count = 0
    success = 0
    for app_name in app_names:
        logger.info('Checking application %s ...' % app_name)
        app = Application(app_name)
        if app.is_running():
            check_names = app.check_names()
            for check_name in check_names:
                count += 1
                url = app.check_url(check_name)
                pattern = app.check_success_pattern(check_name)
                logger.info('Check "%s": Matching %s with pattern "%s"' % (check_name, url, pattern))
                findings = []
                try:
                    resp = requests.get(url, verify=False)
                    findings = re.findall('.*%s.*' % pattern, resp.text)
                    logger.debug('findings:%s' % findings)
                except requests.exceptions.RequestException as e:
                    logger.warning('Problem with request: %s' % e)
                if len(findings) > 0:
                    if details:
                        for line in findings:
                            logger.info(line)
                    logger.info('OK')
                    success += 1
                else:
                    logger.info('FAIL')
        else:
            count += 1
            logger.info('FAIL (app is stopped)')

    logger.info('%s checks executed, %s failed' % (count, count - success))
    if success == count:
        logger.info('Check result: OK')
        return 0
    else:
        logger.warn('Check result: FAIL')
        return 1


@safutils.method_trace
def rm(app_name):
    if app_name not in get_all_app_names():
        raise SafExecutionException('No app found with name %s' % app_name)

    saf.tx._deactivate(app_name)

    return 0
