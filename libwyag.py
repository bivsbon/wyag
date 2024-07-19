from argparser_spec import argparser
from obj import *
from file_utils import *

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
                class_ = GitCommit
            case b'tree':
                class_ = GitTree
            case b'tag':
                class_ = GitTag
            case b'blob':
                class_ = GitBlob
            case '_':
                raise Exception(f"Unknown type {fmt.decode('ascii')} for object {sha}")

    return class_(raw[y+1:])


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
