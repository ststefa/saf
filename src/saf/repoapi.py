import saf

from saf.packages import gitlab

from saf.exceptions import *

from . import safutils

import logging

logger = logging.getLogger(__name__)


class RepoApi(object):
    """ RepoApi subclasses encapsulate the communication with the Repo server. They should not
        contain any SAF specific logic. Think of it as a generic "git (server) connector", one
         subclass for any type of server """
    from abc import ABCMeta, abstractmethod
    __metaclass__ = ABCMeta

    @abstractmethod
    def exists_branch(self, branch):
        """ return true if branch exists, false otherwise """
        raise NotImplementedError

    @abstractmethod
    def get_pending_merge_requests(self, branch):
        """ return a list with zero or more branch names with pending merge requests
            towards branch """
        raise NotImplementedError


class GitlabRepoApi(RepoApi):
    """ Use GitLab as mixin repo"""

    @safutils.method_trace
    def __init__(self):
        for mand_param in ['mixinrepo.gitlab.url', 'mixinrepo.gitlab.token']:
            if mand_param not in saf.config.keys():
                raise SafConfigException('Mandatory GitLab API parameter "%s" missing' % mand_param)
        if not saf.config['mixinrepo.gitlab.url'].startswith('http'):
            raise SafConfigException(
                'Only http(s) allowed for mixinrepo.gitlab.url. Found %s' % saf.config[
                    'mixinrepo.gitlab.url'])
        host_name = saf.config['mixinrepo.gitlab.url'].split('://')[1].split('/')[0]
        logger.debug('host_name:%s' % host_name)
        if host_name not in saf.config['mixinrepo.origin.url']:
            raise SafConfigException(
                'hostname mismatch between mixinrepo.origin.url and mixinrepo.gitlab.url')
        self._connection = gitlab.Gitlab(saf.config['mixinrepo.gitlab.url'],
                                         token=saf.config['mixinrepo.gitlab.token'],
                                         verify_ssl=False)
        gitlab_project = saf.config['mixinrepo.origin.url']
        gitlab_project = gitlab_project[gitlab_project.rindex(':') + 1:]
        gitlab_project = gitlab_project[:-4]
        logger.debug('gitlab_project:%s' % gitlab_project)
        if self._connection.getproject(gitlab_project):
            self._project_id = self._connection.getproject(gitlab_project)["id"]
        else:
            raise SafRepositoryException("Cannot access git project %s on %s" % (
                gitlab_project, saf.config['mixinrepo.gitlab.url']))

    @safutils.method_trace
    def exists_branch(self, branch):
        if self._connection.getbranch(self._project_id, branch):
            return True
        else:
            return False

    @safutils.method_trace
    def get_pending_merge_requests(self, branch):
        if not self.exists_branch(branch):
            raise SafRepositoryException('No branch named "%s" ' % branch)
        result = []
        merge_requests = self._connection.getmergerequests(self._project_id, state='opened')
        for merge_request in merge_requests:
            logger.debug('merge_request:%s' % merge_request)
            if merge_request["target_branch"] == branch:
                if merge_request["source_branch"] not in result:
                    result.append(merge_request["source_branch"])
        logger.debug('result:%s' % result)
        return result


class BitbucketRepoApi(RepoApi):
    """ Use Bitbucket/Stash as mixin repo"""

    @safutils.method_trace
    def __init__(self):
        for mand_param in ['mixinrepo.bitbucket.url', 'mixinrepo.bitbucket.token']:
            if mand_param not in saf.config.keys():
                raise SafConfigException(
                    'Mandatory BitBucket API parameter "%s" missing' % mand_param)

    @safutils.method_trace
    def exists_branch(self, branch):
        raise NotImplementedError

    @safutils.method_trace
    def get_pending_merge_requests(self, branch):
        raise NotImplementedError


class NoneRepoApi(RepoApi):
    """ Use a plain local bare git repo as mixin repo"""

    @safutils.method_trace
    def __init__(self):
        pass

    @safutils.method_trace
    def exists_branch(self, branch):
        return True

    @safutils.method_trace
    def get_pending_merge_requests(self, branch):
        # bare repo cannot do merge requests
        return list()
