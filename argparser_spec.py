import argparse


argparser = argparse.ArgumentParser(description="I am argparser")
argsubparsers = argparser.add_subparsers(title="Commands", dest="command")
argsubparsers.required = True

argsp_init = argsubparsers.add_parser("init", help="Initialize a new empty repository")
argsp_cat_file = argsubparsers.add_parser("cat-file", help="Provide content of repository object")
argsp_hash_object = argsubparsers.add_parser("hash-object",
                                             help="Compute object id and optionally creates a blob from a file")
# init command
argsp_init.add_argument("path",
                        metavar="directory",
                        nargs="?",
                        default=".",
                        help="Where to create the repository")

# cat-file command
argsp_cat_file.add_argument("type",
                            metavar="type",
                            choices=["commit", "tree", "tag", "blob"],
                            help="Specify the type")
argsp_cat_file.add_argument("object",
                            metavar="object",
                            help="The object to display")

# hash-object command
argsp_hash_object.add_argument("-t",
                               metavar="type",
                               dest="type",
                               choices=["commit", "tree", "tag", "blob"],
                               default="blob",
                               help="Specify the type")
argsp_hash_object.add_argument("-w",
                               dest="write",
                               action="store_true",
                               help="Actually write the object into the database")
argsp_hash_object.add_argument("path",
                               help="Read object from <file>")
