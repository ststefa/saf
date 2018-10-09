# ATTENTION! File managed by Puppet. Changes will be overwritten.

class SafException(Exception):
    pass


class SafInitException(SafException):
    pass


class SafConfigException(SafException):
    pass


class SafExecutionException(SafException):
    pass


class SafRepositoryException(SafException):
    pass


class SafTransactionException(SafExecutionException):
    pass
