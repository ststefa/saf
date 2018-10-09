# ATTENTION! File managed by Puppet. Changes will be overwritten.
import ConfigParser
import os
import shutil
import tempfile

import zipfile

import subprocess

import saf.tx

import requests

import saf.repoapi
from saf.exceptions import *

from . import safutils

import logging

logger = logging.getLogger(__name__)

_ssh_opts = '-o IdentityFile=~/.ssh/id_rsa -o StrictHostKeyChecking=no -o BatchMode=yes'


class MixinRepo(object):
    @safutils.method_trace
    def __init__(self, branch):
        for mand_param in ['mixinrepo.origin.url', 'mixinrepo.api.type', 'stage']:
            if mand_param not in saf.config.keys():
                raise SafConfigException('Mandatory repository parameter "%s" missing' % mand_param)
        self.mixin_basedir = os.path.join(saf.config['basedir'], 'var', 'mixin')
        if not os.path.exists(self.mixin_basedir):
            os.makedirs(self.mixin_basedir, mode=0o755)

        if saf.config['mixinrepo.api.type'].lower() == 'gitlab':
            self.api = saf.repoapi.GitlabRepoApi()
        elif saf.config['mixinrepo.api.type'].lower() == 'bitbucket':
            self.api = saf.repoapi.BitbucketRepoApi()
        elif saf.config['mixinrepo.api.type'].lower() == 'none':
            self.api = saf.repoapi.NoneRepoApi()
        else:
            raise SafConfigException(
                'Unsupported mixinrepo.api.type "%s"' % saf.config['mixinrepo.api.type'])

        if not self.api.exists_branch(branch):
            raise SafRepositoryException('No mixin branch named %s' % branch)

        if os.path.exists(os.path.join(self.mixin_basedir, '.git')):

            current_branch_name = safutils.command_stdout(
                'git rev-parse --abbrev-ref HEAD', cwd=self.mixin_basedir)
            logger.debug('current branch_name:%s' % current_branch_name)

            clone_info = safutils.command_stdout(
                'git remote show -n origin', cwd=self.mixin_basedir).split('\n')
            logger.debug('clone_info:%s' % clone_info)
            origin = [line for line in clone_info if 'Fetch URL:' in line]
            logger.debug('origin (pre):%s' % origin)
            if len(origin) != 1:
                raise SafRepositoryException(
                    'Cannot determine origin of mixin clone from %s' % origin)
            origin = origin[0]
            origin = origin[origin.find('Fetch URL:') + 10:].strip()
            logger.debug('origin (post):%s' % origin)

            clone_valid = True
            if origin != saf.config['mixinrepo.origin.url']:
                logger.info('Local mixin origin mismatch  ("%s" != "%s")' % (
                    origin, saf.config['mixinrepo.origin.url']))
                clone_valid = False
            elif current_branch_name != branch:
                logger.info('Local mixin branch mismatch ("%s" != "%s")' % (
                    current_branch_name, branch))
                clone_valid = False
            if not clone_valid:
                logger.debug('Removing local clone')
                safutils.wipe_dir(self.mixin_basedir)

        if os.path.exists(os.path.join(self.mixin_basedir, '.git')):
            safutils.command_rc('git reset --hard HEAD', cwd=self.mixin_basedir)
            safutils.command_rc('git clean -f -d', cwd=self.mixin_basedir)
            safutils.command_rc('git pull', cwd=self.mixin_basedir)
        else:
            safutils.command_rc('git clone --branch %s %s .' % (branch,
                                                                saf.config['mixinrepo.origin.url']),
                                cwd=self.mixin_basedir)

            # TODO:create saf-specific custom ssh keypair; add the pubkey to gitlab "saf_reader";use privkey in git call; make privkey asrun readable (noone else!)

    @safutils.method_trace
    def exists_inode(self, inode_name):
        abs_inode = os.path.join(self.mixin_basedir, inode_name)
        logger.debug('abs_inode:%s' % abs_inode)
        return os.path.exists(abs_inode)

    @safutils.method_trace
    def copy_inode(self, inode_name, target_name):
        abs_inode = os.path.join(self.mixin_basedir, inode_name)
        if not os.path.exists(abs_inode):
            raise SafRepositoryException('No file named %s' % inode_name)
        if os.path.isdir(abs_inode):
            shutil.copytree(abs_inode, os.path.join(target_name, os.path.basename(inode_name)))
        else:
            shutil.copy2(abs_inode, os.path.join(target_name, os.path.basename(inode_name)))

    @safutils.method_trace
    def copy_inode_content(self, inode_name, target_name):
        abs_parent = os.path.join(self.mixin_basedir, inode_name)
        if os.path.exists(abs_parent):
            if not os.path.isdir(abs_parent):
                raise SafRepositoryException('%s is not a directory' % abs_parent)
        else:
            raise SafRepositoryException('No inode named %s' % abs_parent)
        if not os.path.isdir(target_name):
            raise SafRepositoryException('Target directory %s does not exist' % target_name)
        for inode in os.listdir(abs_parent):

            if os.path.isdir(os.path.join(abs_parent, inode)):
                shutil.copytree(os.path.join(abs_parent, inode), os.path.join(target_name, inode))
            else:
                shutil.copy2(os.path.join(abs_parent, inode), os.path.join(target_name, inode))

    @safutils.method_trace
    def get_app_overlay(self, app_name):
        result = None
        overlay_file = os.path.join(self.mixin_basedir, 'apps', app_name, 'overlay.conf')
        logger.debug('overlay_file:%s' % overlay_file)
        if os.path.exists(overlay_file):
            config = ConfigParser.SafeConfigParser()
            config.read(overlay_file)
            if not saf.config['stage'] in config.sections():
                raise SafConfigException('Missing section [%s] in overlay.conf of app %s' % (
                    saf.config['stage'], app_name))
            result = dict(config.items(saf.config['stage']))
        logger.debug('result:%s' % result)
        return result

    @safutils.method_trace
    def get_mixin_overlay(self, mixin_name):
        result = None
        overlay_file = os.path.join(self.mixin_basedir, 'mixins', mixin_name, 'overlay.conf')
        logger.debug('overlay_file:%s' % overlay_file)
        if os.path.exists(overlay_file):
            config = ConfigParser.SafeConfigParser()
            config.read(overlay_file)
            if not saf.config['stage'] in config.sections():
                raise SafConfigException('Missing section [%s] in overlay.conf of mixin %s' % (
                    saf.config['stage'], mixin_name))
            result = dict(config.items(saf.config['stage']))
        logger.debug('result:%s' % result)
        return result


class ArtifactRepo(object):
    @safutils.method_trace
    def __init__(self):
        for mand_param in ['repo.path', 'repo.hostname', 'repo.user']:
            if mand_param not in saf.config.keys():
                raise SafConfigException('Mandatory repository parameter "%s" missing' % mand_param)

    @safutils.method_trace
    def exists_dir(self, path):
        return safutils.command_rc('ssh %s %s@%s test -d %s' % (
            saf.repo._ssh_opts, saf.config['repo.user'], saf.config['repo.hostname'],
            os.path.join(saf.config['repo.path'], path)), assert_rc=False)

    @safutils.method_trace
    def ls(self, path):
        return safutils.command_rc('ssh %s %s@%s "ls %s"' % (
            saf.repo._ssh_opts, saf.config['repo.user'], saf.config['repo.hostname'],
            os.path.join(saf.config['repo.path'], path)), silent=False)

    @safutils.method_trace
    def ll(self, path):
        return safutils.command_rc('ssh %s %s@%s "ls -l %s"' % (
            saf.repo._ssh_opts, saf.config['repo.user'], saf.config['repo.hostname'],
            os.path.join(saf.config['repo.path'], path)), silent=False)

    @safutils.method_trace
    def find(self, path, pattern):
        return safutils.command_rc('ssh %s %s@%s "find %s -name %s"' % (
            saf.repo._ssh_opts, saf.config['repo.user'], saf.config['repo.hostname'],
            os.path.join(saf.config['repo.path'], path), pattern), silent=False)

    @safutils.method_trace
    def upload_recursive(self, from_dir, to_dir):
        return safutils.command_rc(
            'scp -q -r %s %s %s@%s:%s' % (
                saf.repo._ssh_opts, from_dir, saf.config['repo.user'], saf.config['repo.hostname'],
                os.path.join(saf.config['repo.path'], to_dir)))

    @safutils.method_trace
    def delete_recursive(self, del_dir):
        return safutils.command_rc('ssh %s %s@%s rm -fr %s' % (
            saf.repo._ssh_opts, saf.config['repo.user'], saf.config['repo.hostname'],
            os.path.join(saf.config['repo.path'], del_dir)))

    @safutils.method_trace
    def download_recursive(self, from_dir, to_dir):
        return safutils.command_rc(
            'scp -q -r %s %s@%s:%s/. %s/.' % (
                saf.repo._ssh_opts, saf.config['repo.user'], saf.config['repo.hostname'],
                os.path.join(saf.config['repo.path'], from_dir), to_dir))


@safutils.method_trace
def ls(path):
    repo = ArtifactRepo()
    repo.ls(path)


@safutils.method_trace
def ll(path):
    repo = ArtifactRepo()
    repo.ll(path)


@safutils.method_trace
def find(path, pattern):
    repo = ArtifactRepo()
    repo.find(path, pattern)


@safutils.method_trace
def pull(app_name, app_version, ignore_mr=False, deploy=False, iknow=False, branch=None):
    repo = ArtifactRepo()

    if not repo.exists_dir('%s' % app_name):
        raise SafRepositoryException('No such application: %s' % app_name)
    if not repo.exists_dir('%s/%s' % (app_name, app_version)):
        raise SafRepositoryException(
            'No such version for application %s: %s' % (app_name, app_version))

    if branch is None:
        branch = saf.config['stage']
    mixin_repo = MixinRepo(branch)

    pending_from = mixin_repo.api.get_pending_merge_requests(branch)
    if len(pending_from) > 0:
        logger.info(
            'There are open merge requests from the following branch(es) towards your branch (%s):' %
            branch)
        for from_branch in pending_from:
            logger.info('    %s' % from_branch)
        if ignore_mr:
            logger.info(
                'These changes should probably be merged. Ignoring for now on your request.')
        else:
            logger.info('Please merge and retry (or use --ignore_mr to ignore).')
            return 1

    # Create new tx
    app_tx = saf.tx.Transaction()
    app_tx.meta['app_name'] = app_name
    app_tx.meta['app_version'] = app_version
    app_tx.meta['stage'] = saf.config['stage']
    app_tx.meta['tx_type'] = 'new'

    tmp_dir_name = tempfile.mkdtemp(prefix=app_name, dir=saf.temp_dir)

    # ...then add artifact...
    repo.download_recursive('%s/%s' % (app_name, app_version), tmp_dir_name)
    app_tx.add_directory_content(tmp_dir_name, parent_dir='instance')
    safutils.wipe_dir(tmp_dir_name)

    mixin_repo.copy_inode('apps/%s/app.conf' % app_name, tmp_dir_name)
    app_vars = mixin_repo.get_app_overlay(app_name)
    if app_vars is not None:
        safutils.render_template('%s/app.conf' % tmp_dir_name, app_vars)
    app_conf = safutils.parse_kv_file('%s/app.conf' % tmp_dir_name)
    os.rename('%s/app.conf' % tmp_dir_name, '%s/conf' % tmp_dir_name)
    app_tx.add_directory_content(tmp_dir_name)
    safutils.wipe_dir(tmp_dir_name)

    # ...then overlay with all mixins in order...
    if 'mixins' in app_conf.keys():
        mixin_names = app_conf['mixins'].split(' ')
        mixin_names = [elem for elem in mixin_names if elem != '']
        logger.debug('mixin_names:%s' % mixin_names)
        for mixin_name in mixin_names:
            if mixin_repo.exists_inode('mixins/%s/overlay' % mixin_name):
                mixin_repo.copy_inode_content('mixins/%s/overlay' % mixin_name, tmp_dir_name)
                mixin_vars = mixin_repo.get_mixin_overlay(mixin_name)
                if mixin_vars is not None:
                    for root, dirs, files in os.walk(tmp_dir_name):
                        for filename in files:
                            safutils.render_template(os.path.join(root, filename), mixin_vars)
                app_tx.add_directory_content(tmp_dir_name, parent_dir='instance')
                safutils.wipe_dir(tmp_dir_name)
            else:
                raise SafConfigException('no mixin named %s' % mixin_name)

    # ...finally overlay with application mixin
    if mixin_repo.exists_inode('apps/%s/overlay' % app_name):
        mixin_repo.copy_inode_content('apps/%s/overlay' % app_name, tmp_dir_name)
        if app_vars is not None:
            for root, dirs, files in os.walk(tmp_dir_name):
                for filename in files:
                    safutils.render_template(os.path.join(root, filename), app_vars)
        app_tx.add_directory_content(tmp_dir_name, parent_dir='instance')
        safutils.wipe_dir(tmp_dir_name)

    app_tx.commit()
    shutil.rmtree(tmp_dir_name)
    logger.info('Created transaction %s' % app_tx.id)
    if deploy:
        return saf.tx.deploy(app_tx.id, iknow=iknow)
    else:
        return 0


@safutils.method_trace
def push(app_name, app_version, artifact_url):
    repo = ArtifactRepo()

    if not repo.exists_dir('%s' % app_name):
        raise SafRepositoryException('No such application: %s' % app_name)
    if repo.exists_dir('%s/%s' % (app_name, app_version)):
        raise SafRepositoryException(
            'Version %s already exists for applciation %s.' % (app_version, app_name))

    work_dir = tempfile.mkdtemp(prefix='zip', dir=saf.temp_dir)
    logger.debug('work_dir:%s' % work_dir)

    # http://stackoverflow.com/questions/10123929/python-requests-fetch-a-file-from-a-local-url
    requests_session = requests.session()
    requests_session.mount('file://', safutils.LocalFileAdapter())

    # http://stackoverflow.com/questions/13137817/how-to-download-image-using-requests
    try:
        response = requests_session.get(artifact_url, stream=True)
        if response.status_code == 200:
            zip_file_name = os.path.join(work_dir, 'download.zip')
            with open(zip_file_name, 'wb') as out_file:
                shutil.copyfileobj(response.raw, out_file)
        else:
            # http://docs.python-requests.org/en/master/user/quickstart/
            response.raise_for_status()
    except requests.RequestException as e:
        raise SafRepositoryException('Problem with URL: %s' % e)

    zfile = zipfile.ZipFile(zip_file_name)
    for name in zfile.namelist():
        # (dirname, filename) = os.path.split(name)
        # target_dirname = os.path.join(work_dir, dirname)
        # if not os.path.exists(target_dirname):
        #    os.makedirs(target_dirname)
        # zfile.extract(name, target_dirname)
        zfile.extract(name, work_dir)
    os.remove(zip_file_name)

    for root, dirs, files in os.walk(work_dir):
        for dir_name in dirs:
            dir_abs = os.path.join(root, dir_name)
            perms = os.stat(dir_abs).st_mode & 0o0777
            new_perms = (perms | 0o0700) & 0o0755
            if perms != new_perms:
                logger.info('Changing dir permissions of %s from %o to %o' % (
                    dir_abs[len(work_dir) + 1:], perms, new_perms))
                os.chmod(dir_abs, new_perms)
        for file_name in files:
            file_abs = os.path.join(root, file_name)
            # TODO: find more pythonic way to determine filetype
            p1 = subprocess.Popen(['file', '-b', file_abs], stdout=subprocess.PIPE)
            p2 = subprocess.Popen(['grep', 'executable'], stdin=p1.stdout, stdout=subprocess.PIPE)
            result = p2.communicate()
            if len(result[0]) > 0:
                perms = os.stat(file_abs).st_mode & 0o0777
                new_perms = perms | 0o0700
                if perms != new_perms:
                    logger.info('Changing file permissions of %s from %o to %o' % (
                        file_abs[len(work_dir) + 1:], perms, new_perms))
                    os.chmod(file_abs, new_perms)

    repo.upload_recursive(work_dir, '%s/%s' % (app_name, app_version))
    logger.info('Added new version "%s" of application %s' % (app_version, app_name))
    shutil.rmtree(work_dir)
    return 0


@safutils.method_trace
def rmversion(app_name, app_version):
    repo = ArtifactRepo()

    if not repo.exists_dir('%s' % app_name):
        raise SafRepositoryException('No such application: %s' % app_name)
    if not repo.exists_dir('%s/%s' % (app_name, app_version)):
        raise SafRepositoryException(
            'No such version for application %s: %s' % (app_name, app_version))

    if repo.delete_recursive('%s/%s' % (app_name, app_version)):
        logger.info('Removed version "%s" of application %s' % (app_version, app_name))
    else:
        logger.error('Could not remove version "%s" of application %s' % (app_version, app_name))

    return 0
