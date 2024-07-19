import configparser
import os
import file_utils


class GitRepository(object):
    """A Git Repository"""
    worktree = None
    gitdir = None
    conf = None

    def __init__(self, path, force=False):
        self.worktree = path
        self.gitdir = os.path.join(path, ".git")

        if not (force or os.path.isdir(self.gitdir)):
            raise Exception(f"Not a git repository {path}")

        # Read config
        self.conf = configparser.ConfigParser()
        cf = file_utils.repo_file(self, "config")

        if cf and os.path.exists(cf):
            self.conf.read([cf])
        elif not force:
            raise Exception("Config file missing")

        if not force:
            vers = int(self.conf.get("core", "repositoryformatversion"))
            if vers != 0:
                raise Exception(f"Unsupported repositoryformatversion {vers}")


class GitObject(object):
    def __init__(self, data=None):
        if data is not None:
            self.deserialize(data)
        else:
            self.init()

    def serialize(self):
        """
        This function MUST be implemented by subclasses.
        It must read the object's content from self.data, a byte string, and do whatever it takes
        to convert it into a meaningful representation. What exactly that means depend on each subclass.
        """
        raise NotImplementedError("Unimplemented")

    def deserialize(self, data):
        raise NotImplementedError("Unimplemented")

    def init(self):
        pass


class GitCommit(GitObject):
    pass


class GitTree(GitObject):
    pass


class GitTag(GitObject):
    pass


class GitBlob(GitObject):
    fmt = b'blob'

    def serialize(self):
        return self.blobdata

    def deserialize(self, data):
        self.blobdata = data
