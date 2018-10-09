# ATTENTION! File managed by Puppet. Changes will be overwritten.
import difflib
import filecmp
import glob
import os
import random
import re
import shutil
import sre_constants
import string
import tempfile

import subprocess

import time

import saf
from . import safutils

from saf.exceptions import *

import logging

logger = logging.getLogger(__name__)


class Transaction(safutils.IKnowhow):
    """ A transaction object represents a deployable application instance. Transactions have
        three states:

        open
        indoubt
        closed

        A new transaction (i.e. a transaction object created with tx_id=None) is assigned a new unique id.
        It will be initially empty and indoubt. Then files can be added to it using
        tx.add_directory_content(). Once all files are added you tx.commit() the transaction and
        it will turn its state to closed.
        An existing transaction (i.e. a transaction object created with tx_id!=None) will be
        immediately closed
        As a result, a transaction is immutable

        A transaction is transferred to a running application instance using tx.activate()
        """
    @safutils.method_trace
    def __init__(self, tx_id=None):
        if tx_id is None:
            self._indoubt = True
            self._closed = False

            # http://stackoverflow.com/questions/2257441/random-string-generation-with-upper-case-letters-and-digits-in-python#2257449
            chars = string.lowercase + string.digits
            while True:
                self.id = ''.join(random.choice(chars) for _ in range(8))
                if self.id not in get_transaction_ids():
                    break

            self.basedir = os.path.join(saf.config['basedir'], 'transactions', self.id)
            self._tmp_dir_name = tempfile.mkdtemp(prefix=self.id, dir=saf.temp_dir)

            self.meta = dict()

            self.meta['create_user'] = \
                subprocess.Popen(["logname"], stdout=subprocess.PIPE).communicate()[
                    0].rstrip()
            # >= 2.7 syntax
            # self.meta['create_user'] = subprocess.check_output("logname").rstrip()

            self.meta['create_time'] = time.strftime(saf.time_format)
            self.meta['tx_version'] = saf.__txversion__
        else:
            self._indoubt = False
            self._closed = True
            if tx_id not in get_transaction_ids():
                raise SafExecutionException(
                    'No transaction with id %s' % tx_id)
            self.id = tx_id
            self.basedir = os.path.join(saf.config['basedir'], 'transactions', self.id)
            self._assert_valid()
            try:
                self.meta = saf.safutils.parse_kv_file(os.path.join(self.basedir, 'meta'))
                for meta in ['app_name', 'stage', 'app_version', 'tx_type']:
                    if meta not in self.meta.keys():
                        raise SafConfigException(
                            'Cannot load transaction. Metadata "%s" missing' % meta)
                self._config = safutils.parse_kv_file(os.path.join(self.basedir, 'conf'))
                self._knowhow = dict([(key, self._config[key]) for key in self._config.keys() if
                                      key.startswith('knowhow.tx')])
                # use nicer dict comprehension syntax in py2.7+ instead of above dict()
                # self._knowhow = {key: self._config[key] for key in self._config.keys() if key.startswith('knowhow.tx')}
                logger.debug('self.knowhow:%s' % self.knowhow)
            except SafConfigException as e:
                raise SafTransactionException(
                    'Cannot load incomplete transaction %s: %s' % (tx_id, e))

    @safutils.method_trace
    def add_directory_content(self, dir_name, parent_dir='.'):
        """
        Recursively add contents of dir_name to transaction. Overwrite any existing files in
        transaction and log.info the diff
        :param dir_name: Directory to add from
        :param parent_dir: Put dir_name contents in transaction subdir parent_dir
        :raises SafTransactionException If transaction is indoubt or if any OSError
        """
        if not self._indoubt:
            raise SafTransactionException('Persisted transactions are immutable')

        try:
            if not os.path.exists(os.path.join(self._tmp_dir_name, parent_dir)):
                os.mkdir(os.path.join(self._tmp_dir_name, parent_dir))

            for src_root, src_dirs, src_files in os.walk(dir_name):
                dst_root = os.path.join(self._tmp_dir_name, parent_dir,
                                        src_root[len(dir_name) + 1:])
                for src_dir in src_dirs:
                    dst_dir = os.path.join(dst_root, src_dir)
                    if not os.path.exists(dst_dir):
                        logger.debug('mkdir %s' % dst_dir)
                        os.mkdir(dst_dir)
                for src_file in src_files:
                    from_file = os.path.join(src_root, src_file)
                    to_file = os.path.join(dst_root, src_file)
                    logger.debug('copy %s %s' % (from_file, to_file))
                    if os.path.exists(to_file):
                        logger.info(
                            'Overlaying existing %s' % os.path.join(src_root[len(dir_name) + 1:],
                                                                    src_file))
                        if filecmp.cmp(from_file, to_file):
                            logger.info('(files are identical)')
                        else:
                            # http://stackoverflow.com/questions/977491/comparing-two-txt-files-using-difflib-in-python
                            diff_result = difflib.unified_diff(open(to_file).readlines(),
                                                               open(from_file).readlines())
                            logger.info(''.join(diff_result))
                    shutil.copy2(from_file, to_file)
        except OSError as e:
            raise SafTransactionException(e)

    @safutils.method_trace
    def open(self):
        if not self._closed:
            raise SafTransactionException('Transaction already open')
        self._closed = False

    @safutils.method_trace
    def commit(self):
        if self._closed:
            raise SafTransactionException(
                'Cannot commit, transaction closed')

        for meta in ['app_name', 'stage', 'app_version', 'create_user', 'create_time']:
            if meta not in self.meta.keys():
                raise SafTransactionException(
                    'Cannot commit transaction. Metadata incomplete ("%s" missing)' % meta)

        try:
            if self._indoubt:
                logger.debug('persisting indoubt transaction from %s to %s' % (
                    self._tmp_dir_name, self.basedir))
                os.mkdir(self.basedir)
                for inode in os.listdir(self._tmp_dir_name):
                    logger.debug(
                        'mv "%s" "%s"' % (os.path.join(self._tmp_dir_name, inode), self.basedir))
                    shutil.move(os.path.join(self._tmp_dir_name, inode), self.basedir)
                os.rmdir(self._tmp_dir_name)

            with open(os.path.join(self.basedir, 'meta'), 'w') as meta_file:
                metadata = list(
                    "%s=%s\n" % (item, self.meta[item]) for item in sorted(self.meta.keys()))
                logger.debug('metadata:%s' % metadata)
                meta_file.writelines(metadata)

            self._assert_valid()
            self._indoubt = False
            self._closed = True

        except Exception as e:
            if self._indoubt:
                logger.debug('purging indoubt transaction while commit')
                if self._tmp_dir_name is not None:
                    if os.path.exists(self._tmp_dir_name):
                        logger.debug('rmtree %s' % self._tmp_dir_name)
                        shutil.rmtree(self._tmp_dir_name)
                if os.path.exists(self.basedir):
                    logger.debug('rmtree %s' % self.basedir)
                    shutil.rmtree(self.basedir)
            raise SafTransactionException('Error while persisting transaction: %s' % e)

    @safutils.method_trace
    def activate(self):
        abs_target_path = os.path.join(saf.config['basedir'], 'apps', self.meta['app_name'])
        logger.debug('abs_target_path:%s' % abs_target_path)
        if os.path.exists(abs_target_path):
            raise SafTransactionException(
                'Cannot activate transaction, %s exists' % abs_target_path)

        # copy instance first
        shutil.copytree(os.path.join(self.basedir, 'instance'), abs_target_path)

        # copy others
        # tx/<name> becomes app/<appname>.<name>
        for inode in os.listdir(self.basedir):
            abs_inode = os.path.join(self.basedir, inode)
            logger.debug('abs_inode:%s' % abs_inode)
            if inode == 'instance':
                continue
            else:
                if os.path.isdir(abs_inode):
                    shutil.copytree(abs_inode, '%s.%s' % (abs_target_path, inode))
                else:
                    shutil.copy2(abs_inode, '%s.%s' % (abs_target_path, inode))

    @safutils.method_trace
    def delete(self):
        if not self._closed:
            raise SafTransactionException('Cannot delete open transaction')

        try:
            shutil.rmtree(self.basedir)
        except OSError as e:
            raise SafTransactionException(e)

    def _assert_valid(self):
        if not os.path.exists(os.path.join(self.basedir, 'instance')):
            raise SafTransactionException('instance missing')
        if not os.path.exists(os.path.join(self.basedir, 'conf')):
            raise SafTransactionException('conf missing')
        if not os.path.exists(os.path.join(self.basedir, 'meta')):
            raise SafTransactionException('meta missing')

    @safutils.method_trace
    def __del__(self):
        if self._indoubt:
            logger.debug('purging indoubt transaction')
            if self._tmp_dir_name is not None:
                if os.path.exists(self._tmp_dir_name):
                    shutil.rmtree(self._tmp_dir_name)
        if not self._closed:
            logger.warning('Discarding changes in open transaction %s. ' % self.id)

    @safutils.method_trace
    def knowhow(self):
        return safutils.ImmutableDict(self._knowhow)


@safutils.method_trace
def get_transaction_ids():
    tx_basedir = os.path.join(saf.config['basedir'], 'transactions')
    transaction_ids = os.listdir(tx_basedir)
    transaction_ids = [tx_name for tx_name in transaction_ids if
                       os.path.isdir(os.path.join(tx_basedir, tx_name))]
    logger.debug('transaction_ids:%s' % transaction_ids)
    return sorted(transaction_ids)


@safutils.method_trace
def get_transactions_by_regex(app_regex):
    tx_list = []
    try:
        pattern = re.compile('^%s$' % app_regex)
    except sre_constants.error as e:
        raise SafExecutionException('Invalid regular expression: %s' % e)
    for tx_id in get_transaction_ids():
        tx = Transaction(tx_id)
        if re.search(pattern, tx.meta['app_name']):
            tx_list.append(tx)
    logger.debug('tx_list:%s' % tx_list)
    return tx_list


@safutils.method_trace
def get_transactions_by_name(app_name):
    tx_list = []
    for tx_id in get_transaction_ids():
        tx = Transaction(tx_id)
        if tx.meta['app_name'] == app_name:
            tx_list.append(tx)
    logger.debug('tx_list:%s' % tx_list)
    return tx_list


@safutils.method_trace
def ls(app_regex, asjson=False):
    try:
        pattern = re.compile('^%s$' % app_regex)
    except sre_constants.error as e:
        raise SafExecutionException('Invalid regular expression: %s' % e)

    tx_data = dict()
    for tx_id in get_transaction_ids():
        try:
            tx = Transaction(tx_id)
            if re.search(pattern, tx.meta['app_name']):
                tx_data[tx_id] = dict()
                for prop in ['app_name', 'app_version', 'tx_type', 'create_time']:
                    tx_data[tx_id][prop] = tx.meta[prop]
                tx_data[tx_id]['size'] = saf.safutils.directory_size(tx.basedir)
        except SafTransactionException as e:
            logger.warn(e)

    if asjson:
        logger.info(tx_data)
    else:
        tx_list = [['ID', 'APP', 'VERSION', 'TYPE', 'TIME', 'SIZE']]
        for tx_id in tx_data.keys():
            tx_list.append(
                [tx_id, tx_data[tx_id]['app_name'], tx_data[tx_id]['app_version'],
                 tx_data[tx_id]['tx_type'],
                 tx_data[tx_id]['create_time'], tx_data[tx_id]['size']])
        formatted_lines = saf.safutils.align_columns(tx_list)
        for line in formatted_lines:
            logger.info(line)
    return 0


@safutils.method_trace
def info(txid, asjson=False):
    if asjson:
        result = dict()
        try:
            tx = Transaction(txid)
            result[txid] = tx.meta
        except SafTransactionException as e:
            result[txid] = str(e)
        logger.info(result)
    else:
        try:
            tx = Transaction(txid)
            logger.info('%s:' % tx.id)
            for key in sorted(tx.meta.keys()):
                logger.info('    %s : %s' % (key, tx.meta[key]))
        except SafTransactionException as e:
            logger.info('%s (%s)' % (txid, e))
    return 0


@safutils.method_trace
def rm(appname_or_txid):
    for specifier in appname_or_txid:
        if specifier in get_transaction_ids():
            # do not use Transaction object because invalid transactions could not be deleted
            tx_dir = os.path.join(saf.config['basedir'], 'transactions', specifier)
            logger.info('Removing transaction %s' % specifier)
            shutil.rmtree(tx_dir)
        else:
            transactions = get_transactions_by_name(specifier)
            if len(transactions) == 0:
                raise SafExecutionException(
                    'No transaction matching appname or id %s (no regex allowed)' % specifier)
            else:
                for transaction in transactions:
                    logger.info(
                        'Removing transaction %s (app %s)' % (
                            transaction.id, transaction.meta['app_name']))
                    transaction.delete()
    return 0


@safutils.method_trace
def _deactivate(app_name):
    app = saf.app.Application(app_name)
    if app.is_running():
        raise SafExecutionException('Cannot deactivate running app %s' % app_name)
    backout_tx = Transaction()
    logger.info(
        'Moving deployed instance of %s to backout transaction %s' % (app_name, backout_tx.id))

    for key in ['app_name', 'app_version', 'stage']:
        backout_tx.meta[key] = app.meta[key]
    backout_tx.meta['tx_type'] = 'backout'

    # TODO: Ugly hack bypassing Transaction class integrity
    shutil.move(app.basedir, os.path.join(backout_tx._tmp_dir_name, 'instance'))
    # app/<appname>.<name> becomes tx/<name>
    for inode in glob.glob('%s.*' % app.basedir):
        target_name = inode[len(app.basedir) + 1:]
        logger.debug('mv %s %s' % (inode, os.path.join(backout_tx._tmp_dir_name, target_name)))
        shutil.move(inode, os.path.join(backout_tx._tmp_dir_name, target_name))
    backout_tx.commit()


@safutils.method_trace
def deploy(appname_or_txid, iknow=False):
    if appname_or_txid in get_transaction_ids():
        deploy_tx = Transaction(appname_or_txid)
    else:
        transactions = get_transactions_by_name(appname_or_txid)
        if len(transactions) == 0:
            raise SafExecutionException(
                'No transaction matching appname or id %s' % appname_or_txid)
        elif len(transactions) > 1:
            raise SafExecutionException(
                'Multiple transactions matching %s: %s' % (
                    appname_or_txid, ', '.join([tx.id for tx in transactions])))
        else:
            deploy_tx = transactions[0]

    do_deactivate = False
    if deploy_tx.meta['app_name'] in saf.app.get_app_names(all=True):
        if saf.app.Application(deploy_tx.meta['app_name']).is_running():
            raise SafExecutionException(
                'Cannot deactivate running app %s' % deploy_tx.meta['app_name'])
        else:
            do_deactivate = True

    safutils.assert_knowhow(deploy_tx, 'knowhow.tx.deploy', iknow)

    if do_deactivate:
        # move to backout tx if already deployed
        _deactivate(deploy_tx.meta['app_name'])

    logger.info('Deploying transaction %s (application %s)' % (
        deploy_tx.id, deploy_tx.meta['app_name']))
    deploy_tx.open()

    deploy_tx.meta['deploy_user'] = \
        subprocess.Popen(["logname"], stdout=subprocess.PIPE).communicate()[0].rstrip()
    # >= 2.7 syntax
    # deploy_tx.meta['deploy_user'] = subprocess.check_output("logname").rstrip()
    deploy_tx.meta['deploy_time'] = time.strftime(saf.time_format)
    deploy_tx.commit()
    deploy_tx.activate()
    app = saf.app.Application(deploy_tx.meta['app_name'])
    try:
        logger.info('Starting %s ...' % app.name)
        app.start(iknow)
        logger.info('OK')
        logger.info('Removing transaction %s' % deploy_tx.id)
        deploy_tx.delete()
        return 0
    except SafExecutionException as e:
        logger.info('Failed to start: %s' % e)
        logger.info('Preserving transaction %s' % deploy_tx.id)
        return 1


@safutils.method_trace
def _diff_recursive(left, right, left_alias, right_alias):
    def check_and_diff(left_file_abs, right_file_abs):
        if not os.path.exists(right_file_abs):
            logger.info(
                'Only in %s: %s\n' % (left_alias, left_file_abs[len(saf.config['basedir']) + 1:]))
            return
        if not os.path.exists(left_file_abs):
            logger.info(
                'Only in %s: %s\n' % (right_alias, right_file_abs[len(saf.config['basedir']) + 1:]))
            return
        if os.path.isdir(left_file_abs):
            return
        if not filecmp.cmp(left_file_abs, right_file_abs, shallow=False):
            if saf.safutils.is_binary(left_file_abs) or saf.safutils.is_binary(right_file_abs):
                logger.info('--- %s : %s' % (left_alias, left_file_abs[len(left) + 1:]))
                logger.info('+++ %s : %s' % (right_alias, right_file_abs[len(right) + 1:]))
                logger.info('(binary files differ)\n')
            else:
                # http://stackoverflow.com/questions/977491/comparing-two-txt-files-using-difflib-in-python
                diff_result = difflib.unified_diff(open(left_file_abs).readlines(),
                                                   open(right_file_abs).readlines(),
                                                   fromfile='%s : %s' % (left_alias,
                                                                         left_file_abs[
                                                                         len(saf.config[
                                                                                 'basedir']) + 1:]),
                                                   tofile='%s : %s' % (right_alias,
                                                                       right_file_abs[
                                                                       len(saf.config[
                                                                               'basedir']) + 1:]),
                                                   )
                logger.info(''.join(diff_result))

    if os.path.isfile(left):
        check_and_diff(left, right)
    else:
        # content compare left to right
        for left_root, left_dirs, left_files in os.walk(left):
            right_root_abs = os.path.join(right, left_root[len(left) + 1:])
            # for left_dir in left_dirs:
            #    left_dir_abs = os.path.join(left_root_abs, left_dir)
            #    right_dir_abs = os.path.join(right_root_abs, left_dir)
            #    check_and_diff(left_dir_abs, right_dir_abs)
            for left_file in left_files:
                left_file_abs = os.path.join(left_root, left_file)
                right_file_abs = os.path.join(right_root_abs, left_file)
                check_and_diff(left_file_abs, right_file_abs)

        # report right-only (content already compared above)
        for right_root, right_dirs, right_files in os.walk(right):
            right_root_abs = right_root
            left_root_abs = os.path.join(left, right_root[len(right) + 1:])
            # for right_dir in right_dirs:
            #    right_dir_abs = os.path.join(right_root_abs, right_dir)
            #    left_dir_abs = os.path.join(left_root_abs, right_dir)
            #    if not os.path.exists(left_dir_abs):
            #        check_and_diff(left_dir_abs, right_dir_abs)
            for right_file in right_files:
                right_file_abs = os.path.join(right_root_abs, right_file)
                left_file_abs = os.path.join(left_root_abs, right_file)
                check_and_diff(left_file_abs, right_file_abs)
    return 0


@safutils.method_trace
def diff(txid_1, txid_2=None):
    if txid_2 is None:
        if txid_1 not in get_transaction_ids():
            raise SafExecutionException(
                'No transaction with id %s' % txid_1)
        else:
            transaction = Transaction(txid_1)
            app_name = transaction.meta['app_name']
            if app_name not in saf.app.get_all_app_names():
                raise SafExecutionException('Cannot diff %s. App %s not deployed.' % (
                    transaction.id, app_name))
            else:
                app = saf.app.Application(app_name)
                _diff_recursive(os.path.join(transaction.basedir, 'instance'), app.basedir,
                                left_alias=transaction.id, right_alias=app.name)
                tx_inodes = os.listdir(transaction.basedir)
                tx_inodes.remove('instance')
                for tx_inode in tx_inodes:
                    tx_inode_abs = os.path.join(transaction.basedir, tx_inode)
                    app_inode_abs = '%s.%s' % (app.basedir, tx_inode)
                    _diff_recursive(tx_inode_abs, app_inode_abs, left_alias=transaction.id,
                                    right_alias=app.name)
                apps_base = os.path.join(saf.config['basedir'], 'apps')
                app_inodes = glob.glob1(apps_base, '%s.*' % app.name)
                for app_inode in app_inodes:
                    app_inode_abs = os.path.join(apps_base, app_inode)
                    tx_inode_abs = os.path.join(transaction.basedir, app_inode[len(app.name) + 1:])
                    _diff_recursive(app_inode_abs, tx_inode_abs, left_alias=app.name,
                                    right_alias=transaction.id)
    else:
        for tx_id in [txid_1, txid_2]:
            if tx_id not in get_transaction_ids():
                raise SafExecutionException(
                    'No transaction with tx_id %s' % tx_id)
        else:
            transaction1 = Transaction(txid_1)
            transaction2 = Transaction(txid_2)
            _diff_recursive(left=transaction1.basedir, right=transaction2.basedir,
                            left_alias=transaction1.id, right_alias=transaction2.id)
    return 0
