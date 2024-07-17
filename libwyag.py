from argparser_spec import argparser
import collections
import configparser

from datetime import datetime
import grp, pwd
from fnmatch import fnmatch
import hashlib
from math import ceil
import os
import re
import sys
import zlib


def main(argv=sys.argv[1:]):
    args = argparser.parse_args(argv)
    match args.command:
        case "init":
            cmd_init(args)
        case "cat-file":
            cmd_cat_file(args)
        case "hash-object":
            cmd_hash_object(args)


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
        cf = repo_file(self, "config")

        if cf and os.path.exists(cf):
            self.conf.read([cf])
        elif not force:
            raise Exception("Config file missing")

        if not force:
            vers = int(self.conf.get("core", "repositoryformatversion"))
            if vers != 0:
                raise Exception(f"Unsupported repositoryformatversion {vers}")


def repo_path(repo, *path):
    """Compute path under repo's gitdir."""
    return os.path.join(repo.gitdir, *path)


def repo_file(repo, *path, mkdir=False):
    """
    Same as repo_path, but create dirname(*path) if absent. For example,
    repo file (r, "refs", "remotes", "origin", "HEAD") will create .git/refs/remotes/origin.
    """
    if repo_dir(repo, *path[:-1], mkdir=mkdir):
        return repo_path(repo, *path)


def repo_dir(repo, *path, mkdir=False):
    """Same as repo_path, but mkdir if absent if mkdir"""
    path = repo_path(repo, *path)

    if os.path.exists(path):
        if os.path.isdir(path):
            return path
        else:
            raise Exception(f"Not a directory {path}")

    if mkdir:
        os.makedirs(path)
        return path
    else:
        return None


def repo_create(path):
    repo = GitRepository(path, True)

    # First, we make sure the path either doesn't exist or is an empty dir
    if os.path.exists(repo.worktree):
        if not os.path.isdir(repo.worktree):
            raise Exception(f"{path} is not a directory")
        if os.path.isdir(repo.gitdir) and os.listdir(repo.gitdir):
            raise Exception(f"{path} is not empty")
    else:
        os.mkdir(repo.worktree)

    assert repo_dir(repo, "branches", mkdir=True)
    assert repo_dir(repo, "objects", mkdir=True)
    assert repo_dir(repo, "refs", "tags", mkdir=True)
    assert repo_dir(repo, "refs", "heads", mkdir=True)
    assert repo_dir(repo, "branches", mkdir=True)

    # .git/description
    with open(repo_file(repo, "description"), "w") as f:
        f.write("Unnamed repository; edit this file 'description' to name the repository.\n")

    # .git/HEAD
    with open(repo_file(repo, "HEAD"), "w") as f:
        f.write("ref: refs/heads/master\n")

    with open(repo_file(repo, "config"), "w") as f:
        config = repo_default_config()
        config.write(f)

    return repo


def repo_default_config():
    ret = configparser.ConfigParser()

    ret.add_section("core")
    ret.set("core", "repositoryformatversion", "0")
    ret.set("core", "filemode", "false")
    ret.set("core", "bare", "false")

    return ret


def cmd_init(args):
    repo_create(args.path)


def repo_find(path=".", required=True):
    path = os.path.realpath(path)

    if os.path.isdir(os.path.join(path, ".git")):
        return GitRepository(path)

    # If we haven't returned, recurse in parent, if w
    parent = os.path.realpath(os.path.join(path, ".."))

    if parent == path:
        # Bottom case
        # os.path.join("/", "..") == "/"
        # If parent==path, then path is root
        if required:
            raise Exception(f"No git directory")
        else:
            return None

    # Recursive case
    return repo_find(parent, required)


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


def object_read(repo, sha):
    """Read object sha from Git repository repo. Return a GitObject whose exact type depends on the object."""
    path = repo_file(repo, "objects", sha[0:2], sha[2:])

    if not os.path.exists(path):
        return None

    with open (path, "rb") as f:
        raw = zlib.decompress(f.read())

        # Read object type
        x = raw.find(b' ')
        fmt = raw[0:x]

        # Read and validate object size
        y = raw.find(b'\x00', x)
        size = int(raw[x:y].decode("ascii"))
        if size != len(raw)-y-1:
            raise Exception(f"Malformed object {sha}: bad length")

        # Pick constructor
        match fmt:
            case b'commit':
                c = GitCommit
            case b'tree':
                c = GitTree
            case b'tag':
                c = GitTag
            case b'blob':
                c = GitBlob
            case '_':
                raise Exception(f"Unknown type {fmt.decode('ascii')} for object {sha}")

    return c(raw[y+1:])


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


def object_write(obj, repo=None):
    # Serialize object data
    data = obj.serialize()
    # Add header
    result = obj.fmt + b' ' + str(len(data)).encode('ascii') + b'\x00' + data
    # Compute hash
    sha = hashlib.sha1(data).hexdigest()

    if repo:
        # Compute path
        path = repo_file(repo, "objects", sha[0:2], sha[2:], mkdir=True)

        if not os.path.exists(path):
            with open(path, "wb") as f:
                # Compress and write
                f.write(zlib.compress(result))

    return sha


def cmd_cat_file(args):
    repo = repo_find()
    cat_file(repo, args.object, fmt=args.type.encode())


def cat_file(repo, obj, fmt=None):
    obj = object_read(repo, object_find(repo, obj, fmt=fmt))
    sys.stdout.buffer.write(obj.serialize())


def object_find(repo, name, fmt=None, follow=None):
    """Name resolution function, give it a name that refers to object (can be full hash, short hash, tag)
    and it will return the full hash"""
    return name


def cmd_hash_object(args):
    repo = repo_find() if args.write else None

    with open(args.path, "rb") as fd:
        sha = object_hash(fd, args.type.encode(), repo)
        print(sha)


def object_hash(fd, fmt, repo=None):
    data = fd.read()

    # Choose constructor according to fmt argument
    match fmt:
        case b'commit':
            obj = GitCommit(data)
        case b'tree':
            obj = GitTree(data)
        case b'tag':
            obj = GitTag(data)
        case b'blob':
            obj = GitBlob(data)
        case b'_':
            raise Exception(f"Unknown type {fmt}")

    return object_write(obj, repo)
