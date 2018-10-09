# ATTENTION! File managed by Puppet. Changes will be overwritten.

from __future__ import print_function

import ConfigParser
import StringIO
import inspect
import itertools
import os
import re
import shlex
import shutil
import subprocess
import threading
import urllib

import saf

from saf.exceptions import *

from saf.packages import em
from saf.packages import requests

import logging

logger = logging.getLogger(__name__)


def method_trace(fn):
    from functools import wraps

    @wraps(fn)
    def wrapper(*my_args, **my_kwargs):
        logger.debug(
            '>>> %s(%s ; %s ; %s)' % (fn.__name__, inspect.getargspec(fn), my_args, my_kwargs))
        out = fn(*my_args, **my_kwargs)
        logger.debug('<<< %s' % fn.__name__)
        return out

    return wrapper


@method_trace
def command_rc(cmd, cwd=None, assert_rc=True, silent=True):
    """
    Execute shell command and (optionally, depending on silent flag) print stdout. Return rc
    :param cmd: String containing the command (e.g. "git pull")
    :param cwd: The directory which will be cwd for the command
    :param assert_rc: If True then raise exception if command rc!=0
    :param silent: If True then just log.debug(stdout). If False then log.info(stdout)
    :raises SafConfigException If rc!=0 (and assert_rc=True)
    :return: True if rc=0, False otherwise
    """

    # TODO: Cleverly combine this method with command_stdout()
    proc = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            cwd=cwd)

    out, err = [x.decode("utf-8") for x in proc.communicate()]
    logger.debug('returned from command with proc.returncode=%s' % proc.returncode)

    # remove trailing linefeeds
    out = out.rstrip()
    err = err.rstrip()

    if silent:
        logger.debug('stdout:%s' % out)
    else:
        logger.info('%s' % out)

    logger.debug('stderr:%s' % err)

    if assert_rc and proc.returncode != 0:
        raise SafExecutionException(
            "Error (rc:%s) when running %s: %s" % (proc.returncode, cmd, err))

    return not proc.returncode


@method_trace
def command_stdout(cmd, cwd=None, assert_rc=True):
    """
    Execute shell command. Return stdout
    :param cmd: String containing the command (e.g. "git pull")
    :param cwd: The directory which will be cwd for the command
    :param assert_rc: If True then raise exception if command rc!=0
    :raises SafConfigException If rc!=0 (and assert_rc=True)
    :return: stdout of process call
    """

    proc = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            cwd=cwd)
    out, err = [x.decode("utf-8") for x in proc.communicate()]

    # remove trailing linefeeds
    out = out.rstrip()
    err = err.rstrip()

    logger.debug('returned from command with proc.returncode=%s' % proc.returncode)
    logger.debug('stdout:%s' % out)
    logger.debug('stderr:%s' % err)

    if assert_rc and proc.returncode != 0:
        raise SafExecutionException(
            "Error (rc:%s) when running %s: %s" % (proc.returncode, cmd, err))

    return out


@method_trace
def run_process(cmd, cwd=None, log_output=True):
    """
    Run process. Tail output forever. This method is used exclusively for that purpose.
    It should be possible to not have a separate function for this purpose but I was unable to
    figure that out. It's rather tricky. If you want to try make sure to test all possible cases
    :param cmd: The command string (e.g. "git pull")
    :param cwd: The directory which will be cwd for the command
    :param log_output: Whether to additionally capture the output in the logfile or just print it
    :raises SafExecutionException
    :return: True if shell command $?=0, False otherwise
    """
    if type(cmd) is not str:
        raise SafExecutionException('run_process requires a string arg')

    cmd = shlex.split(cmd)

    if cwd:
        logger.debug('running "%s" in directory %s' % (cmd, cwd))
    else:
        logger.debug('running "%s"' % cmd)

    process = None
    try:

        if log_output:
            out_func = logger.info
        else:
            out_func = print

        # http://stackoverflow.com/questions/375427/non-blocking-read-on-a-subprocess-pipe-in-python/437888#437888
        # http://stackoverflow.com/questions/12057794/python-using-popen-poll-on-background-process#12058609
        # Also tried several approaches based on
        # http://stackoverflow.com/questions/12523044/how-can-i-tail-a-log-file-in-python#12523371
        # but was not able to solve the "tail -f problem" (aka continuous stdout processing)
        # Also failed with p.communicate()
        def process_stream(myprocess, stream):  # output-consuming thread
            # stream is either stdout or stderr pipe of the process
            next_line = None
            buf = ''
            while True:
                out = stream.read(1)
                if out == '' and myprocess.poll() is not None:
                    break
                if out != '':
                    if out == '\n':
                        next_line = buf
                        buf = ''
                    else:
                        buf += out
                if not next_line:
                    continue
                line = next_line
                next_line = None

                out_func(line)
            stream.close()

        process = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)

        stdout_poller = threading.Thread(target=process_stream, args=(process, process.stdout,))
        stdout_poller.daemon = True
        stdout_poller.start()

        stderr_poller = threading.Thread(target=process_stream, args=(process, process.stderr,))
        stderr_poller.daemon = True
        stderr_poller.start()

        # while process.poll() is None:
        #    logger.debug('running')
        #    time.sleep(1)
        process.wait()
        logger.debug('returned from wait() with process.returncode=%s' % process.returncode)

        if stdout_poller and stdout_poller.is_alive():
            logger.debug('joining stdout_poller')
            stdout_poller.join()
            logger.debug('joined stdout_poller')
        if stderr_poller and stderr_poller.is_alive():
            logger.debug('joining stderr_poller')
            stderr_poller.join()
            logger.debug('joined stderr_poller')

    except OSError as e:
        logger.error("Error in call: %s" % e)
        raise SafExecutionException(e)
    except KeyboardInterrupt:
        logger.debug('KeyboardInterrupt')
    finally:
        rc = 255
        termination = 'irregular'
        if process and process.returncode is not None:
            rc = process.returncode
            termination = 'regular'
        logger.debug('%s exit, rc: %s' % (termination, rc))
        # negated shell returncode equals python boolean
        # i.e. $?=0 returns True, $?!=0 returns False
        return not rc


@method_trace
def _get_secret():
    """
    Retrieve contents of SAF secret file (/app/saf/conf/secret)
    :raises SafConfigException if secret not present
    :return: string representing the SAF secret
    """
    secret_file_name = os.path.join(saf.base_path, 'conf', 'secret')
    secret = None
    try:
        with open(secret_file_name, 'r') as secret_file:
            for line in secret_file:
                if line.startswith('#'):
                    continue
                else:
                    secret = line
                    break
        if secret is None:
            raise SafConfigException('Missing secret')
        return secret
    except IOError as e:
        raise SafConfigException(e)


@method_trace
def parse_kv_file(file_name):
    """
    Retrieve contents of plain key=value file
    :param file_name: The name of the file
    :raises SafConfigException if the file could not be parsed
    :return: dict containing all key/value pairs
    """
    try:
        parser = ConfigParser.ConfigParser()
        # http://stackoverflow.com/questions/19359556/configparser-reads-capital-keys-and-make-them-lower-case#19359720
        parser.optionxform = str
        with open(file_name) as stream:
            # http://stackoverflow.com/questions/2885190/using-pythons-configparser-to-read-a-file-without-section-name
            fakefile = StringIO.StringIO("[top]\n" + stream.read())
            parser.readfp(fakefile)
            result = dict(parser.items('top'))
            logger.debug('result:%s' % result)
            return result
    except IOError as e:
        raise SafConfigException('Could not parse file: %s' % e)


@method_trace
def encrypt(literal):
    literal = ' '.join(literal)
    inf_key = itertools.chain.from_iterable(itertools.repeat(_get_secret()))
    result = ''.join(chr(ord(a) ^ ord(b)) for a, b in zip(literal, inf_key)).encode(
        'base64').strip()

    return '{ENC}%s' % result


@method_trace
def decrypt(literal):
    if literal.startswith('{ENC}'):
        inf_key = itertools.chain.from_iterable(itertools.repeat(_get_secret()))
        result = ''.join(
            chr(ord(a) ^ ord(b)) for a, b in zip(literal[5:].decode('base64'), inf_key))
        return result
    else:
        raise SafExecutionException("Decrypted values must start with {ENC}")


@method_trace
def wipe_dir(dir_name):
    """
    delete contents of dir_name but leave dir_name in place
    :param dir_name: The name of the directory to wipe contents from
    :raises SafExecutionException if IOError occurs
    """

    # http://stackoverflow.com/questions/185936/delete-folder-contents-in-python#185941
    for the_file in os.listdir(dir_name):
        file_path = os.path.join(dir_name, the_file)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except IOError as e:
            raise SafExecutionException(e)


@method_trace
def render_template(file_name, overlay_dict):
    """
    Render mixin template to resolved file using empy interpreter
    :param file_name: The name of the file
    :param overlay_dict: Dictionary containing key=value pairs to replace
    :raises SafConfigException if the file could not be rendered
    :return: dict containing all key/value pairs
    """
    if is_binary(file_name):
        logger.debug('is_binary:%s' % file_name)
        return

    with open(file_name) as f:
        data = f.read()
        f.close()

    # overlay_dict must not be modified because of is_confidential check
    temp_dict = dict(overlay_dict)

    is_confidential = False
    for key in temp_dict.keys():
        if temp_dict[key].startswith('{ENC}'):
            temp_dict[key] = decrypt(temp_dict[key])
            if re.search("@\(?%s\)?" % key, data) is not None:
                is_confidential = True
    logger.debug('is_confidential:%s' % is_confidential)

    interpreter = em.Interpreter()
    try:
        out = interpreter.expand(data, temp_dict)
    except Exception as e:
        raise SafExecutionException("Problems rendering %s: %s" % (file_name, str(e)))

    with open(file_name, 'w') as f:
        if is_confidential:
            os.chmod(f.name, 0o600)
        f.write(out)
        f.close()


# http://stackoverflow.com/questions/3685195/line-up-columns-of-numbers-print-output-in-table-format#3685943
@method_trace
def align_columns(lines, is_left_align=True):
    cols = map(lambda *row: [str(field) or '' for field in row], *lines)
    widths = [max(len(field) for field in col) for col in cols]
    format = ['%%%s%ds' % ('-' if is_left_align else '', width) for width in widths]
    return ['  '.join(format[:len(row)]) % tuple(row) for row in lines]


# http://stackoverflow.com/questions/898669/how-can-i-detect-if-a-file-is-binary-non-text-in-python
@method_trace
def is_binary(file_name):
    text_chars = bytearray([7, 8, 9, 10, 12, 13, 27]) + bytearray(range(0x20, 0x7f)) + bytearray(
        range(0x80, 0x100))
    f = open(file_name, 'rb')
    data = f.read(1024)
    return bool(data.translate(None, text_chars))


# http://stackoverflow.com/questions/3229419/pretty-printing-nested-dictionaries-in-python
@method_trace
def prettyprint_dict(d, indent=4):
    for key, value in sorted(d.iteritems()):
        line = ' ' * indent + str(key)
        if isinstance(value, dict):
            logger.info(line + ':')
            prettyprint_dict(value, indent * 2)
        else:
            logger.info(line + ' : ' + str(value))


# http://stackoverflow.com/questions/1392413/calculating-a-directory-size-using-python
@method_trace
def directory_size(path):
    total_size = 0
    seen = set()

    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                stat = os.stat(fp)
            except OSError:
                continue
            if stat.st_ino in seen:
                continue
            seen.add(stat.st_ino)
            total_size += stat.st_size
    return total_size  # size in bytes


# http://stackoverflow.com/questions/10123929/python-requests-fetch-a-file-from-a-local-url
class LocalFileAdapter(requests.adapters.BaseAdapter):
    """Protocol Adapter to allow Requests to GET file:// URLs

    TODO: Properly handle non-empty hostname portions.
    """

    @staticmethod
    @method_trace
    def _chkpath(method, path):
        """Return an HTTP status for the given filesystem path."""
        if method.lower() in ('put', 'delete'):
            return 501, "Not Implemented"  # TODO
        elif method.lower() not in ('get', 'head'):
            return 405, "Method Not Allowed"
        elif os.path.isdir(path):
            return 400, "Path '%s' is not a file" % path
        elif not os.path.isfile(path):
            return 404, "File '%s' not found" % path
        elif not os.access(path, os.R_OK):
            return 403, "Access to '%s' denied" % path
        else:
            return 200, "OK"

    @method_trace
    def send(self, req, **kwargs):
        """Return the file specified by the given request

        @type req: C{PreparedRequest}
        @todo: Should I bother filling `response.headers` and processing
               If-Modified-Since and friends using `os.stat`?
        """
        path = os.path.normcase(os.path.normpath(urllib.url2pathname(req.path_url)))
        logger.debug('path:%s' % path)
        response = requests.Response()

        response.status_code, response.reason = self._chkpath(req.method, path)
        if response.status_code == 200 and req.method.lower() != 'head':
            try:
                response.raw = open(path, 'rb')
            except (OSError, IOError) as err:
                response.status_code = 500
                response.reason = str(err)

        if isinstance(req.url, bytes):
            response.url = req.url.decode('utf-8')
        else:
            response.url = req.url

        response.request = req
        response.connection = self

        return response

    @method_trace
    def close(self):
        pass


@method_trace
def assert_knowhow(knowhow_object, knowhow_key, auto_acknowledge):
    """ Ensure that non-standard, project-specific SAF operating instructions are known
     to the operator """
    action = knowhow_key.split('.')[-1]
    if knowhow_key in knowhow_object.knowhow().keys():
        if auto_acknowledge:
            logger.info(
                "This app requires special %s handling described in %s. You acknowledged that you are familiar with these instructions." %
                (action, knowhow_object.knowhow()[knowhow_key]))
        else:
            logger.info(
                "This app requires special %s handling described in %s. Please make sure to familiarize yourself with these instructions before proceeding." %
                (action, knowhow_object.knowhow()[knowhow_key]))
            answer = raw_input("Ready to proceed (Y/n)? ")
            if answer not in ['y', 'Y', '']:
                raise SafExecutionException('Please read the instructions before proceeding')
    else:
        logger.debug("Nothing to know")


class IKnowhow(object):
    """ Derived classes must implement a knowhow() method which has to return
      a dict object containing knowhow asserts taken from app.conf """

    from abc import ABCMeta, abstractmethod
    __metaclass__ = ABCMeta

    @abstractmethod
    def knowhow(self):
        """ Return a dict containing knowhow_key / -_value pairs. The
        dict should be readonly """
        raise NotImplementedError


class ImmutableDict(dict):
    """ Use ImmutableDict for handling dicts which are meant to be readonly.
    An attempt to modify the dict leads to AttributeError. This hack is not
    tamper proof! It's just used to remind the coder that he is not meant to
    change the dict """

    def __setitem__(self, key, val):
        raise AttributeError("Dict is immutable")
