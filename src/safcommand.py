#!/usr/bin/python
# ATTENTION! File managed by Puppet. Changes will be overwritten.

""" SAF commandline interface
Utility parser module to analyze commandline parameters and activate the appropriate SAF module
"""
import argparse

import os
import subprocess
import sys

from saf.packages import yaml

import saf, saf.app, saf.repo, saf.tx

from saf.exceptions import *

import logging, logging.config

logger = logging.getLogger(__name__)


class IsEqualFilter(logging.Filter):
    def __init__(self, level, name=""):
        logging.Filter.__init__(self, name)
        self.level = level

    def filter(self, record):
        # non-zero return means we log this message
        return 1 if record.levelno == self.level else 0


class IsNotEqualFilter(logging.Filter):
    def __init__(self, level, name=""):
        logging.Filter.__init__(self, name)
        self.level = level

    def filter(self, record):
        # non-zero return means we log this message
        return 1 if record.levelno != self.level else 0


asjson = argparse.ArgumentParser(add_help=False)
asjson.add_argument('-j', '--asjson', action='store_true', help='Produce json formatted output')

iknow = argparse.ArgumentParser(add_help=False)
iknow.add_argument('--iknow', action='store_true',
                   help='Acknowledge that you already read and understood project-specific operating instructions which may exist. If not specified then you will be interactively prompted with the URL of these instructions')


def _populate_app_parser(parent_parser):
    sub_parser = parent_parser.add_subparsers(dest='action', title='SAF application commands',
                                              description='Applications are deployed transactions which can be started and stopped. Use these commands to view or change their runtime status')

    selector = argparse.ArgumentParser(add_help=False,
                                       formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    # http://stackoverflow.com/questions/7869345/how-to-make-python-argparse-mutually-exclusive-group-arguments-without-prefix
    app_selector_group = selector.add_mutually_exclusive_group(required=False)
    app_selector_group.add_argument('-a', '--all', action='store_true',
                                    help='All apps. Default for the commands ls, ps, status')
    app_selector_group.add_argument('app_regex', nargs='?',
                                    help='A python regular expression specifying the app name(s)')

    bootstart = argparse.ArgumentParser(add_help=False,
                                        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    bootstart.add_argument('-b', '--bootstart', action='store_true',
                           help='Consider only apps which are enabled for automatic start upon OS boot (i.e. bootstart=true in /app/saf/apps/<app>.conf)')

    p = sub_parser.add_parser('ls', parents=[bootstart, selector, asjson],
                              help='List specified apps',
                              description='List specified apps with their deployment metadata')
    p.add_argument('-d', '--details', action='store_true',
                   help='Show app meta details (version, build time,...)')
    p.set_defaults(func=saf.app.ls)

    p = sub_parser.add_parser('tail', parents=[bootstart, selector],
                              help='Tail logfiles of app(s) to stdout forever',
                              description='"Tail -f"\'s all files which reside inide the log/ directories of apps to stdout forever (i.e. until Ctrl-C is pressed)')
    p.set_defaults(func=saf.app.tail)

    p = sub_parser.add_parser('start', parents=[bootstart, selector, iknow],
                              help='Sequentially start app(s)',
                              description='Start app(s) sequentially one by one. Will abort on the first error it encounters. Trying to start a started app is not considered an error')
    p.set_defaults(func=saf.app.start)

    p = sub_parser.add_parser('stop', parents=[bootstart, selector, iknow],
                              help='Sequentially stop app(s)',
                              description='Stop app(s) sequentially one by one. Will abort on the first error it encounters. Trying to stop a stopped app is not considered an error')
    p.set_defaults(func=saf.app.stop)

    p = sub_parser.add_parser('restart', parents=[bootstart, selector, iknow],
                              help='Sequentially restart app(s)',
                              description='Restart app(s) sequentially one by one. Will abort on the first error it encounters. Trying to stop a stopped app or to start a started app is not considered an error.')
    p.set_defaults(func=saf.app.restart)

    p = sub_parser.add_parser('status', parents=[bootstart, selector, asjson],
                              help='Posix style status of app(s)',
                              description='Shows a Posix style summary of the app(s) to get a compact view of runtime status')
    p.set_defaults(func=saf.app.status)

    p = sub_parser.add_parser('rm', help='Uninstall application and move it to a backout transaction',
                              description='Removes an application by moving it from the apps area into a newly created backout transaction')
    p.add_argument('app_name', help='Name of stopped application')
    p.set_defaults(func=saf.app.rm)

    p = sub_parser.add_parser('ps', parents=[selector],
                              help='List processes of (running) apps',
                              description='List processes of (running) apps. The CPU consumption is an average of used CPU cycles in the last second (100% = 1 CPU fully utilized)')
    p.set_defaults(func=saf.app.ps)

    p = sub_parser.add_parser('pinfo', parents=[asjson],
                              help='Process details of the pid(s) of app',
                              description='Show detailed information about all the PIDs of an app (output can be quite lengthy)')
    p.add_argument('app_name', help='Name of (running) app')
    p.set_defaults(func=saf.app.pinfo)

    p = sub_parser.add_parser('check', parents=[bootstart, selector],
                              help='Query configured checks of app(s)',
                              description='Query configured checks of app(s) for success literal (case sensitive)')
    p.add_argument('-d', '--details', action='store_true',
                   help='Output matching places in HTTP response')
    p.set_defaults(func=saf.app.check)


def _populate_repo_parser(parent_parser):
    sub_parser = parent_parser.add_subparsers(dest='action', title='SAF repository commands',
                                              description='Push and pull applications from the SAF repositories')

    p = sub_parser.add_parser('ls', help='List contents of application repo',
                              formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument('path', default='.', nargs='?',
                   help='A path in the repo. Wildcards are supported.')
    p.set_defaults(func=saf.repo.ls)

    p = sub_parser.add_parser('ll', help='List contents of application repo with details',
                              formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument('path', default='.', nargs='?',
                   help='A path in the repo. Wildcards are supported.')
    p.set_defaults(func=saf.repo.ll)

    p = sub_parser.add_parser('find', help='Find files in application repo',
                              formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument('path', default='.', help='Path in the repo')
    p.add_argument('pattern', default='.', help='Filename pattern to search')
    p.set_defaults(func=saf.repo.find)

    p = sub_parser.add_parser('pull', parents=[iknow],
                              help='Get app version from artifact repo, overlay with contents from mixin repo and create a transaction')
    p.add_argument('app_name', help='Name of app which exists in the repo')
    p.add_argument('app_version', help='Version of app')
    p.add_argument('--ignore_mr', action='store_true',
                   help='Ignore existing merge-requests towards the branch which is used for this pull')
    p.add_argument('--deploy', action='store_true',
                   help='Immediately deploy after successful pull.')
    p.add_argument('--branch',
                   help='Use this git branch from mixin repository instead of default branchname=stagename')
    p.set_defaults(func=saf.repo.pull)

    p = sub_parser.add_parser('push',
                              help='Retrieve application artifact from specified url, unpack it and store the result in the artifact-repo with specified version')
    p.add_argument('app_name', help='Name of application (must exist in repo)')
    p.add_argument('app_version', help='Version of app (must not yet exist in repo)')
    p.add_argument('artifact_url', help='A curl-compatible URL from where to obtain the artifact')
    p.set_defaults(func=saf.repo.push)

    p = sub_parser.add_parser('rmversion',
                              help='Remove app version from artifact repo')
    p.add_argument('app_name', help='Name of app')
    p.add_argument('app_version', help='Version of app')
    p.set_defaults(func=saf.repo.rmversion)


def _populate_tx_parser(parent_parser):
    sub_parser = parent_parser.add_subparsers(dest='action', title='SAF transaction commands',
                                              description='Transactions are stage-specific instances created by downloading and merging content from the artifact- and mixin-repo. A transaction is turned into a running application by deploying it.')

    p = sub_parser.add_parser('ls', parents=[asjson], help='List transactions',
                              formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument('app_regex', default='.*', nargs='?',
                   help='Only show transactions for apps matching app_regex')
    p.set_defaults(func=saf.tx.ls)

    p = sub_parser.add_parser('deploy', parents=[iknow],
                              help='Deploy (i.e. activate and start) transaction')
    p.add_argument('appname_or_txid',
                   help='Transaction to deploy either specified by app name or transaction id (no regex allowed)')
    p.set_defaults(func=saf.tx.deploy)

    p = sub_parser.add_parser('rm', help='Remove transaction(s)')
    p.add_argument('appname_or_txid', nargs='+',
                   help='One or more transactions either specified by app name(s) or transaction id(s) (no regex allowed)')
    p.set_defaults(func=saf.tx.rm)

    p = sub_parser.add_parser('info', parents=[asjson], help='Detailed info about a transaction')
    p.add_argument('txid', help='A transaction id (no regex allowed)')
    p.set_defaults(func=saf.tx.info)

    p = sub_parser.add_parser('diff',
                              help='Compare transaction with deployed app or with other transaction)')
    p.add_argument('txid_1', help='Transaction to compare')
    p.add_argument('txid_2', nargs='?',
                   help='Compare txid_1 with txid_2. If not specified then diff txid_1 with deployed app')
    p.set_defaults(func=saf.tx.diff)

    # export tar
    # import tar


def init_parser():
    #    """saf
    # |__app
    # |  |__ls
    # |  |__...
    # |__repo
    # |  |__ls
    # |  |__...
    # |__tx
    # |  |__ls
    # |  |__...
    # |__encrypt
    # |__decrypt
    # """
    # http://stackoverflow.com/questions/18106327/display-pydocs-description-as-part-of-argparse-help#18107559

    parser = argparse.ArgumentParser(
        description='The Standalone (aka Self-contained) Application Framework ("SAF") is a devops operating and staging concept which standardizes operating tasks (start, stop, deploy ...) while still giving the developer flexibility in the choice of technology.',
        prog='saf', formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog='Choose command or command group')
    parser.add_argument('-c', '--config', default='conf/saf.conf',
                        help='Alternate config file name. Relative paths are interpreted relative to SAF basedir (%s)' % saf.base_path)
    parser.add_argument('-d', '--debug', action='store_true', help='Turn on console debug output')
    parser.add_argument('-v', '--version', action='version', version=saf.__version__)

    root_parsers = parser.add_subparsers(dest='object', title='SAF commands and command groups')

    sub_parser = root_parsers.add_parser('app',
                                         help='Application command group (start, stop, ...)')
    _populate_app_parser(sub_parser)

    sub_parser = root_parsers.add_parser('repo',
                                         help='Repository command group (pull, push, ...)')
    _populate_repo_parser(sub_parser)

    sub_parser = root_parsers.add_parser('tx',
                                         help='Transaction command group (deploy, ls, rm, ...)')
    _populate_tx_parser(sub_parser)

    p = root_parsers.add_parser('encrypt',
                                help='Output encrypted version of plaintext literal')
    p.add_argument('literal', nargs='+',
                   help='The literal to encrypt. All ASCII characters are allowed. Enclose literal in '' to prevent shell expansion. Inline spaces are preserved but consecutive spaces will be collapsed (e.g. "a  b" will become "a b"')
    p.set_defaults(func=saf.safutils.encrypt)

    p = root_parsers.add_parser('decrypt',
                                help='Output decrypted version of encrypted literal')
    p.add_argument('literal', help='The literal to decrypt (must start with "{ENC}")')
    p.set_defaults(func=saf.safutils.decrypt)

    return parser


if __name__ == '__main__':

    with open(os.path.join(saf.base_path, 'lib/logging.yaml')) as data_file:
        log_config = yaml.load(data_file)
        log_filename = log_config['handlers']['file']['filename']
        if log_filename[0] != '/':
            log_config['handlers']['file']['filename'] = os.path.join(saf.base_path, log_filename)
        logging.config.dictConfig(log_config)

    # split console logging up into proper stdout/stderr
    # requires logging config to be setup accordingly (i.e. with stdout/err StreamHandlers)
    # in logging.yaml
    for handler in logger.root.handlers:
        if handler.stream == sys.stdout:
            handler.addFilter(IsEqualFilter(logging.INFO))
        if handler.stream == sys.stderr:
            handler.addFilter(IsNotEqualFilter(logging.INFO))

    logger.debug('sys.argv:%s' % sys.argv)

    # https://docs.python.org/2/library/subprocess.html#module-subprocess
    try:
        logger.debug(
            'logname: %s' % subprocess.Popen(["logname"], stdout=subprocess.PIPE).communicate()[
                0].rstrip())
        # >= 2.7 syntax
        # logger.debug('logname: %s' % subprocess.check_output("logname").rstrip())
    except subprocess.CalledProcessError as e:
        logger.debug('logname: unknown (%s)' % e)

    parser = init_parser()
    args = parser.parse_args()
    logger.debug(logger.handlers)
    if args.debug:
        for handler in logger.root.handlers:
            if handler.__class__ == logging.StreamHandler:
                handler.level = logging.DEBUG

    logger.debug('parser args: %s' % args)

    rc = 0  # master rc
    try:
        conf_file = args.config
        if conf_file[0] != '/':
            conf_file = os.path.join(saf.base_path, conf_file)
        saf.init(conf_file)

        # http://stackoverflow.com/questions/16878315/what-is-the-right-way-to-treat-python-argparse-namespace-as-a-dictionary#16878364
        # http://stackoverflow.com/questions/2465921/how-to-copy-a-dictionary-and-only-edit-the-copy#2465932
        arg_list = dict(vars(args))
        logger.debug('raw arg_list:%s' % arg_list)
        if arg_list['object'] == 'app':
            if arg_list['action'] == 'ls' or arg_list['action'] == 'status':
                if arg_list['app_regex'] is None and arg_list['bootstart'] is False:
                    arg_list['all'] = True
            elif arg_list['action'] == 'ps':
                if arg_list['app_regex'] is None:
                    arg_list['all'] = True
            del arg_list['action']
        if arg_list['object'] == 'repo':
            del arg_list['action']
        if arg_list['object'] == 'tx':
            del arg_list['action']

        del arg_list['config']
        del arg_list['debug']
        del arg_list['func']
        del arg_list['object']

        logger.debug('filtered arg_list:%s' % arg_list)

    except SafInitException as e:
        logger.error('Error while initializing SAF: %s' % e)
        rc = 1

    try:
        # http://stackoverflow.com/questions/334655/passing-a-dictionary-to-a-function-in-python-as-keyword-parameters
        rc = args.func(**arg_list)
    except SafTransactionException as e:
        logger.error('Transaction error: %s' % e)
        rc = 1
    except SafExecutionException as e:
        logger.error('Execution error: %s' % e)
        rc = 1
    except SafConfigException as e:
        logger.error('Configuration error: %s' % e)
        rc = 1
    except SafRepositoryException as e:
        logger.error('Repository error: %s' % e)
        rc = 1
    except KeyboardInterrupt as e:
        logger.debug(e)

    logger.debug('exiting with rc %s' % rc)
    exit(rc)