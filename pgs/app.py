#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function
"""
pgs.app
===============

A bottle webapp for serving static files from a git branch,
or from the local filesystem.

Objectives:

* [x] Learn Bottle
* [x] Serve Static Files (such as ``index.html``)
* [x] Append .html (``file_path = URL + '.html'`` ("``try_files``")
* [x] Serve files from a git branch (or tag/revision)
  (without first checking out to a working directory)
* [x] Serve Last-Modified headers (from git modification times)
* [o] Write toward PyFilesystem interface
* [x] Find commands for listing and reading files in a Git repo
  (e.g. for https://github.com/westurner/pyrpo)

Roadmap:

* [ ] PERF: dulwich, pygit2 (these require dependencies)
* [ ] TST: sensible test cases

"""

import codecs
import collections
import logging
import mimetypes
import os.path
import subprocess
import time
import urllib.parse
from typing import Tuple


import sys
IS_PYTHON2 = sys.version_info.major == 2

if IS_PYTHON2:
    import cgi
    import distutils.spawn
    def html_escape(string, quote=True):
        string = cgi.escape(string, quote=quote)
        if quote:
            string = string.replace("'", "&#x27;")
        return string
    which = distutils.spawn.find_executable

else:
    import html
    import shutil
    html_escape = html.escape
    which = shutil.which

    basestring = str
    long = int

try:
    import bottle
    from bottle import parse_date, request, HTTPResponse, HTTPError, route
except ImportError:
    # import bottle
    from . import bottle
    # from bottle import Bottle, route, run, request, static_file
    from .bottle import parse_date, request, HTTPResponse, HTTPError, route

try:
    import dulwich
    import dulwich.repo
    import dulwich.objects
except ImportError:
    dulwich = None

try:
    import pygit2
except ImportError:
    pygit2 = None

DEBUG = False
DEFAULT_ENCODING = 'UTF8'

log = logging.getLogger('pgs.app')
if DEBUG:
    log.setLevel(logging.DEBUG)
    subp_stderr = subprocess.STDOUT
else:
    log.setLevel(logging.INFO)
    subp_stderr = None  # subprocess.PIPE


def pathjoin(*args, **kwargs):
    """
    Arguments:
        args (list): *args list of paths
            if len(args) == 1, args[0] is not a string, and args[0] is iterable,
            set args to args[0].

    Basically::

        joined_path = u'/'.join(
            [args[0].rstrip('/')] +
            [a.strip('/') for a in args[1:-1]] +
            [args[-1].lstrip('/')])
    """
    log.debug('pathjoin: %r' % list(args))

    def _pathjoin(*args, **kwargs):
        len_ = len(args) - 1
        if len_ < 0:
            raise Exception('no args specified')
        elif len_ == 0:
            if not isinstance(args[0], basestring):
                if hasattr(args[0], '__iter__'):
                    args = args[0]
                    len_ = len(args) - 1
        for i, arg in enumerate(args):
            if not isinstance(arg, basestring):
                raise TypeError("pathjoin() argument must be a string, not %s" % type(arg).__name__)
            if not i:
                yield arg.rstrip('/')
            elif i == len_:
                yield arg.lstrip('/')
            else:
                yield arg.strip('/')
    joined_path = u'/'.join(_pathjoin(*args))
    return sanitize_path(joined_path)



class RepositoryFS(object):
    def exists(self, path):
        # type: (str) -> bool
        raise NotImplementedError()

    def isdir(self, path):
        # type: (str) -> bool
        raise NotImplementedError()

    def isfile(self, path):
        # type: (str) -> bool
        raise NotImplementedError()

    def getinfo(self, path):
        # type: (str) -> dict
        raise NotImplementedError()

    def listdir(self, path, **kwargs):
        # type: (str, **dict) -> list
        raise NotImplementedError()

    def listdirinfo(self, path, **kwargs):
        # type: (str, **dict) -> iter
        raise NotImplementedError()

    def get_fileobj(self, path, *args, **kwargs):
        # type: (str, *tuple, **dict) -> object
        raise NotImplementedError()

    def getsyspath(self, path, allow_none=False):
        # type: (str, bool) -> str
        raise NotImplementedError()


class DirectoryRepositoryFS(RepositoryFS):

    def __init__(self, conf):
        self.conf = conf
        if 'pgs.root_path' not in self.conf:
            raise Exception('must specify root_path')

    @property
    def root_path(self):
        return self.conf['pgs.root_path']

    def prefix_path(self, path):
        path = pathjoin(self.root_path, path)
        return path

    def exists(self, path):
        return os.path.exists(self.prefix_path(path))

    def isdir(self, path):
        return os.path.isdir(self.prefix_path(path))

    def isfile(self, path):
        return os.path.isfile(self.prefix_path(path))

    def getinfo(self, path):
        attrs = collections.OrderedDict()
        stats = os.stat(self.prefix_path(path))
        attrs["size"] = stats.st_size
        attrs["created_time"] = stats.st_ctime
        attrs["accessed_time"] = stats.st_atime
        attrs["modified_time"] = stats.st_mtime
        return attrs

    def listdir(self, path, **kwargs):
        if kwargs:
            raise NotImplementedError()  # ~-> PyFilesystem interface
        return os.listdir(self.prefix_path(path))

    def listdirinfo(self, path, **kwargs):
        if kwargs:
            raise NotImplementedError()  # ~-> PyFilesystem interface
        for p in self.listdir(self.prefix_path(path), **kwargs):
            yield self.getinfo(p)

    def get_fileobj(self, path, *args, **kwargs):
        import io
        kwargs.setdefault('encoding', DEFAULT_ENCODING)
        return io.open(self.prefix_path(path), *args, **kwargs)

    def getsyspath(self, path, allow_none=False):
        return self.prefix_path(path)

    def hassyspath(self, path):
        return bool(self.getsyspath(path))


class SubprocessGitRepositoryFS(RepositoryFS):

    GIT_BIN = os.environ.get('GIT_BIN', which('git'))

    def __init__(self, conf):
        self.conf = conf

    @property
    def repo_path(self):
        return self.conf['pgs.git_repo_path']

    @property
    def repo_rev(self):
        return self.conf['pgs.git_repo_rev']

    def git_cmd(self):
        return [self.GIT_BIN, '-C', self.repo_path]

    def to_git_pathspec(self, path):
        return "%s:%s" % (self.repo_rev, path)

    def prefix_path(self, path):
        path = path.lstrip('/')
        return path

    def exists(self, path):
        path = self.prefix_path(path)
        cmd = self.git_cmd() + ['cat-file', '-e', self.to_git_pathspec(path)]
        retcode = subprocess.call(cmd, stderr=subp_stderr)
        return retcode == 0

    def getsize(self, path: str) -> int:
        path = self.prefix_path(path)
        cmd = self.git_cmd() + ['cat-file', '-s', self.to_git_pathspec(path)]
        return int(subprocess.check_output(cmd))

    def get_author_committer_dates(self, path: str) -> Tuple[int, int]:
        path = self.prefix_path(path)
        cmd = self.git_cmd() + ['log', '-1', "--format=%at %ct",
                                self.repo_rev,
                                '--', path or '.']
        #log.debug("CMD: %r", " ".join(cmd))
        output = subprocess.check_output(cmd, text=True)
        try:
            author_date, committer_date = output.rstrip().split()
            return int(author_date), int(committer_date)
        except ValueError:
            print(('output', output))
            return 0, 0

    def getinfo(self, path):
        path = self.prefix_path(path)
        attrs = collections.OrderedDict()
        attrs["size"] = self.getsize(path)
        _, committer_date = self.get_author_committer_dates(path)
        attrs["created_time"] = committer_date
        attrs["accessed_time"] = committer_date
        attrs["modified_time"] = committer_date
        return attrs

    def get_object_type(self, path):
        path = self.prefix_path(path)
        cmd = self.git_cmd() + ['cat-file', '-t', self.to_git_pathspec(path)]
        output = subprocess.check_output(cmd, universal_newlines=True)
        return output.strip()

    def isdir(self, path):
        return self.get_object_type(path) == 'tree'

    def isfile(self, path):
        return self.get_object_type(path) == 'blob'

    def listdir(self, path, **kwargs):
        path = self.prefix_path(path)
        if kwargs:
            raise NotImplementedError()  # ~-> PyFilesystem interface
        cmd = self.git_cmd() + ['cat-file', '-p', self.to_git_pathspec(path)]
        output = subprocess.check_output(cmd, universal_newlines=True)
        files = []
        for _line in output.splitlines():
            line = _line.strip()
            if line:
                perms, type_, hash, name = line.split(None, 3)
                # yield (name)
                files.append(name)
        return files

    def listdirinfo(self, path, **kwargs):
        if kwargs:
            raise NotImplementedError()  # ~-> PyFilesystem interface
        # TODO: PERF: dirlist and stat the rest
        for p in self.listdir(path, **kwargs):
            yield self.getinfo(pathjoin(path, p))

    def get_fileobj(self, path):
        path = self.prefix_path(path)
        cmd = self.git_cmd() + ['show', self.to_git_pathspec(path)]
        #return subprocess.check_output(cmd)

        p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        
        class _StdoutAdapter(object):
            def __init__(self, process):
                self.p = process

            def read(self, *args, **kwargs):
                return self.p.stdout.read(*args, **kwargs)

            def __iter__(self):
                return iter(self.p.stdout)

            def close(self):
                self.p.stdout.close()
                self.p.terminate()
                self.p.wait()

        return _StdoutAdapter(p)

    def get_contents(self, path):
        path = self.prefix_path(path)
        cmd = self.git_cmd() + ['show', self.to_git_pathspec(path)]
        return subprocess.check_output(cmd)

    def getsyspath(self, path):
        return path


class DulwichGitRepositoryFS(RepositoryFS):

    def __init__(self, repo_path):
        # type: (str) -> None
        self.repo_path = repo_path
        self.repo = dulwich.repo.Repo(self.repo_path)
        self.repo_rev = b'master' # default

    def to_git_path(self, path):
        # type: (str) -> bytes
        return path.lstrip('/').encode('utf-8')

    def get_tree(self):
        commit = self.repo[self.repo_rev]
        return self.repo[commit.tree]

    def _walk_tree(self, path):
        # type: (str) -> object
        tree = self.get_tree()
        if not path or path == '/':
            return tree
        
        parts = path.strip('/').split('/')
        current = tree
        for part in parts:
            if isinstance(current, dulwich.objects.Tree):
                b_part = part.encode('utf-8')
                if b_part in current:
                    mode, sha = current[b_part]
                    current = self.repo[sha]
                else:
                    return None
            else:
                return None
        return current

    def exists(self, path):
        # type: (str) -> bool
        return self._walk_tree(path) is not None

    def isdir(self, path):
        # type: (str) -> bool
        obj = self._walk_tree(path)
        return isinstance(obj, dulwich.objects.Tree)

    def isfile(self, path):
        # type: (str) -> bool
        obj = self._walk_tree(path)
        return isinstance(obj, dulwich.objects.Blob)

    def getinfo(self, path):
        # type: (str) -> dict
        obj = self._walk_tree(path)
        import collections
        import time
        attrs = collections.OrderedDict()
        
        if obj:
            attrs["size"] = obj.raw_length() if isinstance(obj, dulwich.objects.Blob) else 0
        else:
            attrs['size'] = 0

        try: 
            commit = self.repo[self.repo_rev]
        except KeyError:
            raise
            #raise Exception(('Commit not found:', (self.repo_rev,)))
        committer_date = commit.commit_time
        
        attrs["created_time"] = committer_date
        attrs["accessed_time"] = committer_date
        attrs["modified_time"] = committer_date
        return attrs

    def listdir(self, path, **kwargs):
        # type: (str, **dict) -> list
        obj = self._walk_tree(path)
        if isinstance(obj, dulwich.objects.Tree):
            return [item.path.decode('utf-8') for item in obj.items()]
        return []

    def listdirinfo(self, path, **kwargs):
        # type: (str, **dict) -> iter
        from pgs.app import pathjoin
        for p in self.listdir(path, **kwargs):
            yield self.getinfo(pathjoin(path, p))

    def get_fileobj(self, path, *args, **kwargs):
        # type: (str, *tuple, **dict) -> object
        import io
        obj = self._walk_tree(path)
        if isinstance(obj, dulwich.objects.Blob):
            return io.BytesIO(obj.data)
        return io.BytesIO(b'')

    def getsyspath(self, path, allow_none=False):
        # type: (str, bool) -> str
        return path


class Libgit2GitRepositoryFS(RepositoryFS):

    def __init__(self, repo_path):
        # type: (str) -> None
        self.repo_path = repo_path
        self.repo = pygit2.Repository(self.repo_path)
        self.repo_rev = 'master' # default

    def get_tree(self):
        commit = self.repo.revparse_single(self.repo_rev)
        return commit.tree

    def _walk_tree(self, path):
        # type: (str) -> object
        tree = self.get_tree()
        if not path or path == '/':
            return tree
        
        parts = path.strip('/').split('/')
        current = tree
        for part in parts:
            if isinstance(current, pygit2.Tree):
                try:
                    entry = current[part]
                    current = self.repo[entry.id]
                except KeyError:
                    return None
            else:
                return None
        return current

    def exists(self, path):
        # type: (str) -> bool
        return self._walk_tree(path) is not None

    def isdir(self, path):
        # type: (str) -> bool
        obj = self._walk_tree(path)
        return isinstance(obj, pygit2.Tree)

    def isfile(self, path):
        # type: (str) -> bool
        obj = self._walk_tree(path)
        return isinstance(obj, pygit2.Blob)

    def getinfo(self, path):
        # type: (str) -> dict
        obj = self._walk_tree(path)
        import collections
        import time
        attrs = collections.OrderedDict()
        
        if obj:
            attrs["size"] = obj.size if isinstance(obj, pygit2.Blob) else 0
        else:
            attrs['size'] = 0

        commit = self.repo.revparse_single(self.repo_rev)
        committer_date = commit.commit_time
        
        attrs["created_time"] = committer_date
        attrs["accessed_time"] = committer_date
        attrs["modified_time"] = committer_date
        return attrs

    def listdir(self, path, **kwargs):
        # type: (str, **dict) -> list
        obj = self._walk_tree(path)
        if isinstance(obj, pygit2.Tree):
            return [entry.name for entry in obj]
        return []

    def listdirinfo(self, path, **kwargs):
        # type: (str, **dict) -> iter
        from pgs.app import pathjoin
        for p in self.listdir(path, **kwargs):
            yield self.getinfo(pathjoin(path, p))

    def get_fileobj(self, path, *args, **kwargs):
        # type: (str, *tuple, **dict) -> object
        import io
        obj = self._walk_tree(path)
        if isinstance(obj, pygit2.Blob):
            return io.BytesIO(obj.data)
        return io.BytesIO(b'')

    def getsyspath(self, path, allow_none=False):
        # type: (str, bool) -> str
        return path


ADDL_MIMETYPES = [
    ('text/html', '.html'),

    ## Specify text/ MIME types for these file extensions to make files viewable
    ('text/plain', '.txt'),
    ('text/x-rst', '.rst'),
    ('text/markdown', '.md'),
    ('text/x-makefile', '.make'),
    ('text/x-makefile', '.mk'),
    ('text/plain', '.cfg'),

    # ('application/json', '.json'),
    # ('application/ld+json', '.jsonld'),
    ('text/json', '.json'),
    ('text/json', '.jsonld'),

    #('application/yaml', '.yml'),
    #('application/yaml', '.yaml'),
    ('text/yaml', '.yml'),
    ('text/yaml', '.yaml'),

    ('text/csv', '.csv'),

    # Linked Data MIME types (per 5stardata.info)
    ('text/turtle', '.ttl'),
    ('application/n-triples', '.nt'),
    ('application/rdf+xml', '.rdf'),
    ('text/n3', '.n3'),
    ('application/trig', '.trig'),
]

CONFIGURED_MIMETYPES = False


def configure_mimetypes():
    global CONFIGURED_MIMETYPES
    if not CONFIGURED_MIMETYPES:
        for (type_, ext) in ADDL_MIMETYPES:
            mimetypes.add_type(type_, ext)
    CONFIGURED_MIMETYPES = True
    log.debug('configure_mimetypes()')


# bottle app
GIT_REPO_REV_DEFAULT = 'gh-pages'


confs = collections.OrderedDict()
confs['fs-here'] = {
    'pgs.root_path': '.'}
confs['git-here__default'] = {
    'pgs.git_repo_path': '.',
    'pgs.git_repo_rev': GIT_REPO_REV_DEFAULT}
confs['git-here__gh-pages'] = {
    'pgs.git_repo_path': '.',
    'pgs.git_repo_rev': 'gh-pages'}
confs['git-here__master'] = {
    'pgs.git_repo_path': '.',
    'pgs.git_repo_rev': 'master'}


def configure_app(app, conf=None):
    if conf is None:
        conf = {}
    conf['pgs.show_dirlists'] = True
    app.config.update(conf)
    app = configure_FS(app, conf=app.config)
    configure_mimetypes()
    
    # Register routes to this specific app instance
    app.route('<filepath:re:(.*?)@@$>', callback=explicitly_serve_dirlist)
    app.route('<filepath:path>', callback=serve_static_files)
    
    return app


def configure_FS(app, conf=None):
    if conf is None:
        raise ValueError("conf should not be None")
    FS = None
    # if git configuration is found, use git
    if conf.get('pgs.git_repo_path'):
        backend = conf.get('pgs.git_backend', 'subprocess')
        if backend == 'dulwich' and dulwich is not None:
            FS = DulwichGitRepositoryFS(conf.get('pgs.git_repo_path'))
            FS.repo_rev = conf.get('pgs.git_repo_rev', b'master').encode('utf-8') if isinstance(conf.get('pgs.git_repo_rev', 'master'), str) else conf.get('pgs.git_repo_rev', b'master')
        elif backend == 'pygit2' and pygit2 is not None:
            FS = Libgit2GitRepositoryFS(conf.get('pgs.git_repo_path'))
            FS.repo_rev = conf.get('pgs.git_repo_rev', 'master')
        else:
            FS = SubprocessGitRepositoryFS(app.config)
    # otherwise, serve from the filesystem at pgs.root_path
    elif conf.get('pgs.root_path'):
        FS = DirectoryRepositoryFS(app.config)
    app.config['pgs.FS'] = FS
    return app


def make_app(conf=None):
    app = bottle.Bottle()
    return configure_app(app, conf)


# @app.hook('config')
# def on_config_change(key, value):
#    log.debug("config_change: %r = %r" % (key, value))
#    if key == 'root_path':
#        if value:
#            app.config['pgs.FS'] = DirectoryRepositoryFS(app.config)
#    elif key in ('git_repo_path', 'git_repo_rev'):
#        if value:
#            app.config['pgs.FS'] = SubprocessGitRepositoryFS(app.config)

def sanitize_path(path):
    if '\0' in path:
        raise ValueError("Path traversal detected")
        
    # Decode URL-encoded paths, protecting against double/multiple encoding
    decoded_path = urllib.parse.unquote(path)
    prev = path
    while decoded_path != prev:
        prev = decoded_path
        decoded_path = urllib.parse.unquote(decoded_path)
    
    # Normalize backslashes to forward slashes (e.g. Windows paths)
    normalized = decoded_path.replace('\\', '/')
    
    has_leading_slash = normalized.startswith('/')
    has_trailing_slash = normalized.endswith('/') and len(normalized) > 1
    
    # Strip leading slashes so normpath doesn't treat it as absolute
    stripped = normalized.lstrip('/')
    
    # Empty string from stripping
    if not stripped:
        if not path and not decoded_path:
            return ''
        return '/' if has_leading_slash else '.'

    norm = os.path.normpath(stripped)
    
    # Check if the normalized path attempts to navigate out of the root
    if norm.startswith('../') or norm == '..':
        raise ValueError("Path traversal detected")
        
    # Return the normalized, forward-slashed version to prevent symlink bypasses
    # by ensuring backend filesystems resolve lexically evaluated safe paths
    res = norm.replace('\\', '/')
    
    if has_leading_slash and res != '.':
        res = '/' + res
    if has_trailing_slash and not res.endswith('/'):
        res += '/'
        
    return res


def is_hidden_path(path):
    """
    Checks if a path contains any hidden files or directories 
    (starting with '.' but not exactly '.' or '..').
    """
    parts = path.strip('/\\').split('/')
    for part in parts:
        clean_part = part.strip()
        if clean_part.startswith('.') and clean_part not in ['.', '..', '']:
            return True
    return False


def rewrite_path(FS, _path):
    """

    Args:
        _path (str): path to rewrite (in search of index.html)
        root_path (str): filesystem root_path

    """
    path = sanitize_path(_path)
    log.debug('sntpath: %r' % path)
    
    if FS is None:
        raise ValueError("Backend filesystem (FS) is not configured.")

    if FS.exists(path):
        if FS.isdir(path):
            dir_index_html_path = pathjoin(path, 'index.html')
            if (FS.exists(dir_index_html_path)
                    and FS.isfile(dir_index_html_path)):
                path = dir_index_html_path
    else:
        # try appending '.html'
        if not (path.endswith('/') or path.endswith('.html')):
            path_dot_html = path + ".html"
            if FS.exists(path_dot_html) and FS.isfile(path_dot_html):
                path = path_dot_html
    return path


def generate_dirlist_html(FS, filepath):
    """
    Generate directory listing HTML

    Arguments:
        FS (FS): filesystem object to read files from
        filepath (str): path to generate directory listings for

    Keyword Arguments:
        list_dir (callable: list[str]): list file names in a directory
        isdir (callable: bool): os.path.isdir

    Yields:
        str: lines of an HTML table
    """
    yield '<!DOCTYPE html>\n<html>\n<head>\n<meta charset="utf-8">\n'
    yield '<title>%s Directory listing</title>\n' % html_escape(filepath)
    yield '<style>\n'
    yield '  :root { color-scheme: light dark; }\n'
    yield '  body { font-family: monospace; padding: 1rem; }\n'
    yield '  table.dirlist td { padding: 0.25rem 1rem 0.25rem 0; }\n'
    yield '</style>\n</head>\n<body>\n'
    yield '<h1>%s Directory listing</h1>\n' % html_escape(filepath)
    yield '<table class="dirlist">\n'
    if filepath == '/':
        filepath = ''
    for name in sorted(FS.listdir(filepath)):
        full_path = pathjoin(filepath, name)
        if FS.isdir(full_path):
            full_path = full_path + '/'
        yield u'<tr><td><a href="{0}">{0}</a></td></tr>\n'.format(
            html_escape(full_path))  # TODO XXX
    yield '</table>\n</body>\n</html>'


def explicitly_serve_dirlist(filepath):
    # trip leading / and trailing '@@'
    path = filepath[1:][:-2]
    return serve_dirlist(path)


def serve_dirlist(path):
    FS = request.app.config['pgs.FS']
    if FS.exists(path) and FS.isdir(path):
        if request.app.config.get('pgs.show_dirlists'):
            return list(generate_dirlist_html(FS, path))
    return HTTPError(404, 'Not found.')


def serve_static_files(filepath, block_hidden_files=None):
    if not request.app:
        log.debug("request.app is False")
        return

    FS = request.app.config['pgs.FS']
    if block_hidden_files is None:
        block_hidden_files = request.app.config.get('pgs.block_hidden_files', False)

    if filepath == '':
        filepath = '/'  # index.html'
    log.debug("filepath: %r" % filepath)
    path = rewrite_path(FS, filepath)  # or ''  # XXX
    log.debug("rwpath  : %r" % path)
    
    # Hidden files check MUST operate on the fully normalized and parsed path
    if block_hidden_files and is_hidden_path(path):
        return HTTPError(403, "Access denied to hidden files.")

    if FS.exists(path) and FS.isdir(path):
        index_html = pathjoin(path, 'index.html')
        if FS.exists(index_html) and FS.isfile(index_html):
            path = index_html
        else:
            if request.app.config.get('pgs.show_dirlists'):
                return list(generate_dirlist_html(FS, path))
                # TODO: mtime ?

    if isinstance(FS, DirectoryRepositoryFS):
        mimetype, _ = mimetypes.guess_type(path)
        return bottle.static_file(path, root=request.app.config['pgs.root_path'], mimetype=(mimetype or 'text/plain'))
    elif isinstance(FS, (SubprocessGitRepositoryFS, DulwichGitRepositoryFS, Libgit2GitRepositoryFS)):
        # this is mostly derived from bottle.static_file
        # without the RANGE support
        return git_static_file(path, block_hidden_files=block_hidden_files)
    else:
        raise Exception(FS, type(FS))


def git_static_file(filename,
                    mimetype='auto',
                    download=False,
                    charset='UTF-8',
                    block_hidden_files=False):
    """ This method is derived from bottle.static_file:

        Open [a file] and return :exc:`HTTPResponse` with status
        code 200, 305, 403 or 404. The ``Content-Type``, ``Content-Encoding``,
        ``Content-Length`` and ``Last-Modified`` headers are set if possible.
        Special support for ``If-Modified-Since`` [...].

        :param filename: Name or path of the file to send.
        :param mimetype: Defines the content-type header (default: guess from
            file extension)
        :param download: If True, ask the browser to open a `Save as...` dialog
            instead of opening the file with the associated program. You can
            specify a custom filename as a string. If not specified, the
            original filename is used (default: False).
        :param charset: The charset to use for files with a ``text/*``
            mime-type. (default: UTF-8)
    """

    # root = os.path.abspath(root) + os.sep
    # filename = os.path.abspath(pathjoin(root, filename.strip('/\\')))
    filename = filename.strip('/\\')
    
    if block_hidden_files and is_hidden_path(filename):
        return HTTPError(403, "Access denied to hidden files.")

    headers = dict()

    FS = request.app.config['pgs.FS']
    # if not filename.startswith(root):
    #    return HTTPError(403, "Access denied.")
    if not FS.exists(filename):
        return HTTPError(404, "Not found.")
    # if not os.access(filename, os.R_OK):
    # return HTTPError(403, "You do not have permission to access this file.")

    if mimetype == 'auto':
        if download and download is not True:
            mimetype, encoding = mimetypes.guess_type(download)
        else:
            mimetype, encoding = mimetypes.guess_type(filename)
            
        # default to mimetype text/plain (after mimetypes.guess_type)
        if not mimetype:
            mimetype = 'text/plain'
            
        if encoding:
            headers['Content-Encoding'] = encoding

    if mimetype:
        if mimetype[:5] == 'text/' and charset and 'charset' not in mimetype:
            mimetype += '; charset=%s' % charset
        headers['Content-Type'] = mimetype

    if download:
        download = os.path.basename(filename if download else download)
        headers['Content-Disposition'] = 'attachment; filename="%s"' % download

    # stats = os.stat(filename)
    info = FS.getinfo(filename)
    headers['Content-Length'] = clen = info['size']
    lm = time.strftime("%a, %d %b %Y %H:%M:%S GMT",
                       time.gmtime(info['modified_time']))
    headers['Last-Modified'] = lm

    ims = request.environ.get('HTTP_IF_MODIFIED_SINCE')
    if ims:
        ims = parse_date(ims.split(";")[0].strip())
    mtime = info['modified_time']
    if mtime and ims is not None and ims >= int(mtime):
        headers['Date'] = time.strftime("%a, %d %b %Y %H:%M:%S GMT",
                                        time.gmtime())
        return HTTPResponse(status=304, **headers)

    body = '' if request.method == 'HEAD' else FS.get_fileobj(filename)
    # clen
    # headers["Accept-Ranges"] = "bytes"
    # ranges = request.environ.get('HTTP_RANGE')
    # if 'HTTP_RANGE' in request.environ:
    #    ranges = list(parse_range_header(request.environ['HTTP_RANGE'], clen))
    #     if not ranges:
    #         return HTTPError(416, "Requested Range Not Satisfiable")
    #    offset, end = ranges[0]
    #    headers["Content-Range"] = "bytes %d-%d/%d" % (offset, end - 1, clen)
    #    headers["Content-Length"] = str(end - offset)
    #    if body: body = _file_iter_range(body, offset, end - offset)
    #     return HTTPResponse(body, status=206, **headers)
    return HTTPResponse(body, **headers)


def pgs(app, config_obj):
    if not getattr(config_obj, 'root_path', None) and not getattr(config_obj, 'git_repo_path', None):
        raise ValueError("Configuration error: You must specify either a filesystem path (--path) or a git repository (--git) to serve.")

    if config_obj.root_path:
        app.config['pgs.root_path'] = os.path.abspath(
            os.path.expanduser(config_obj.root_path))
    if config_obj.git_repo_path:
        app.config['pgs.git_repo_path'] = os.path.abspath(
            os.path.expanduser(config_obj.git_repo_path))
        app.config['pgs.git_repo_rev'] = config_obj.git_repo_rev
        app.config['pgs.git_backend'] = getattr(config_obj, 'git_backend', 'subprocess')

    if hasattr(config_obj, 'block_hidden_files'):
        app.config['pgs.block_hidden_files'] = config_obj.block_hidden_files

    log.info("app.config: %s" % app.config)
    app = configure_app(app)
    return bottle.run(app,
                      host=config_obj.host,
                      port=config_obj.port,
                      debug=config_obj.debug,
                      reloader=config_obj.reloader)


def get_parser():
    import argparse
    import textwrap

    epilog = """
Usage examples:
  pgs -p ./my/directory
  pgs -g ./my/git/repo -r main
  pgs -g . -r HEAD --git-backend dulwich -P 8080

"""
    prs = argparse.ArgumentParser(
        prog='pgs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Serve a directory or a git revision over HTTP "
                    "with Bottle, WSGI, MIME types, and Last-Modified headers",
        epilog=textwrap.dedent(epilog))

    prs.add_argument('-p', '--path', '--prefix',
                   dest='root_path',
                   help='Filesystem path to serve files from')

    prs.add_argument('-g', '--git',
                   dest='git_repo_path',
                   help='Path to git repo to serve files from')
    prs.add_argument('-r', '--rev',
                   dest='git_repo_rev',
                   help='Git repo revision (commit hash, branch, tag)',
                   default='gh-pages')
    prs.add_argument('--git-backend',
                   dest='git_backend',
                   help='Git backend to use (subprocess, dulwich, pygit2)',
                   default='subprocess')

    prs.add_argument('-H', '--host',
                   dest='host',
                   default='localhost')
    prs.add_argument('-P', '--port',
                   dest='port',
                   default='8082', type=int)
    prs.add_argument('--debug',
                   dest='debug',
                   default=True,
                   action='store_false',
                   help='set bottle debug=False')
    prs.add_argument('--reload',
                   dest='reloader',
                   default=True,
                   action='store_false',
                   help='set bottle reload=False')
    prs.add_argument('--block-hidden-files',
                   dest='block_hidden_files',
                   default=False,
                   action='store_true',
                   help='Do not serve hidden files (defaults to false)')

    prs.add_argument('-v', '--verbose',
                   dest='verbose',
                   action='store_true')
    prs.add_argument('-q', '--quiet',
                   dest='quiet',
                   action='store_true')
    prs.add_argument('-t', '--test',
                   dest='run_tests',
                   action='store_true')

    return prs

def main(argv=1j) -> int:
    import logging
    import sys

    prs = get_parser()
    
    try:
        import argcomplete
        argcomplete.autocomplete(prs)
    except ImportError:
        pass

    _argv = []
    if argv == 1j:
        _argv = sys.argv[1:]
    elif argv is None:
        _argv = []
    else:
        _argv = argv
    opts, args = prs.parse_known_args(args=_argv)

    loglevel = logging.INFO
    if opts.quiet:
        loglevel = logging.ERROR
    if opts.verbose:
        loglevel = logging.DEBUG
        global DEBUG
        DEBUG = True

    logging.basicConfig(
        level=loglevel,
        format='%(asctime)s %(levelname)-6s %(lineno)-4s %(message)s')
    log.setLevel(loglevel)
    for x in ('debug', 'info', 'error'):
        getattr(log, x)("%s ##test##" % x)

    log.debug("opts: %r" % opts)
    log.debug("args: %r" % args)

    if opts.run_tests:
        __argv = [sys.argv[0]] + args
        import unittest
        unittest.main(argv=__argv)
        return 0

    # bottle app
    app = make_app(conf=None)
    _output = pgs(app, opts)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main(argv=1j))