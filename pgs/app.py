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
import cgi
import collections
import codecs
import distutils.spawn
import logging
import mimetypes
import os.path
import subprocess
import time


import bottle
# from bottle import Bottle, route, run, request, static_file
from bottle import parse_date, request, HTTPResponse, HTTPError
try:
    import dulwich
except ImportError:
    dulwich = None

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
            if not isinstance(args, basestring):
                if hasattr(args, '__iter__'):
                    _args = args
                    _args
                    args = args[0]
        for i, arg in enumerate(args):
            if not i:
                yield arg.rstrip('/')
            elif i == len_:
                yield arg.lstrip('/')
            else:
                yield arg.strip('/')
    joined_path = u'/'.join(_pathjoin(*args))
    return sanitize_path(joined_path)


class DirectoryRepositoryFS(object):

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
        kwargs.setdefault('encoding', DEFAULT_ENCODING)
        return codecs.open(self.prefix_path(path), *args, **kwargs)

    def getsyspath(self, path, allow_none=False):
        return self.prefix_path(path)

    def hassyspath(self, path):
        return bool(self.getsyspath(path))


class SubprocessGitRepositoryFS(object):

    GIT_BIN = os.environ.get('GIT_BIN', distutils.spawn.find_executable('git'))

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

    def getsize(self, path):
        path = self.prefix_path(path)
        cmd = self.git_cmd() + ['cat-file', '-s', self.to_git_pathspec(path)]
        return long(subprocess.check_output(cmd))

    def get_author_committer_dates(self, path):
        path = self.prefix_path(path)
        cmd = self.git_cmd() + ['log', '-1', "--format=%at %ct",
                                self.repo_rev,
                                '--', path]
        output = subprocess.check_output(cmd)
        author_date, committer_date = output.rstrip().split()
        return int(author_date), int(committer_date)

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
        return subprocess.check_output(cmd).strip()

    def isdir(self, path):
        return self.get_object_type(path) == 'tree'

    def isfile(self, path):
        return self.get_object_type(path) == 'blob'

    def listdir(self, path, **kwargs):
        path = self.prefix_path(path)
        if kwargs:
            raise NotImplementedError()  # ~-> PyFilesystem interface
        cmd = self.git_cmd() + ['cat-file', '-p', self.to_git_pathspec(path)]
        output = subprocess.check_output(cmd)
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
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        # p.communicate()
        return p.stdout

    def get_contents(self, path):
        path = self.prefix_path(path)
        cmd = self.git_cmd() + ['show', self.to_git_pathspec(path)]
        return subprocess.check_output(cmd)

    def getsyspath(self, path):
        return path


class DulwichGitRepositoryFS(object):

    def __init__(self, repo_path):
        self.repo_path = repo_path
        self.repo = dulwich.repo.Repo(self.repo_path)

    def exists(self, path):
        "TODO"

    def isdir(self, path):
        "TODO"

    def isfile(self, path):
        "TODO"


ADDL_MIMETYPES = [
    ('text/x-makefile', 'Makefile'),
    ('text/x-rst', '.rst'),
    # ('application/json', '.json'),
    ('text/json', '.json'),
    ('text/json', '.jsonld'),
    ('text/csv', '.csv'),
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
    return app


def configure_FS(app, conf=None):
    FS = None
    # if git configuration is found, use git
    if conf.get('pgs.git_repo_path'):
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
    # XXX TODO FIXME
    if '/../' in path:
        raise Exception()
    return path


def rewrite_path(FS, _path):
    """

    Args:
        _path (str): path to rewrite (in search of index.html)
        root_path (str): filesystem root_path

    """
    path = sanitize_path(_path)
    log.debug('sntpath: %r' % path)
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
    yield '<table class="dirlist">'
    if filepath == '/':
        filepath = ''
    for name in FS.listdir(filepath):
        full_path = pathjoin(filepath, name)
        if FS.isdir(full_path):
            full_path = full_path + '/'
        yield u'<tr><td><a href="{0}">{0}</a></td></tr>'.format(
            cgi.escape(full_path))  # TODO XXX
    yield '</table>'


# bottle app

app = make_app(conf=None)


@app.route('<filepath:re:(.*?)@@$>')
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


@app.route('<filepath:path>')
def serve_static_files(filepath):
    FS = request.app.config['pgs.FS']
    if filepath == '':
        filepath = '/'  # index.html'
    log.debug("filepath: %r" % filepath)
    path = rewrite_path(FS, filepath)  # or ''  # XXX
    log.debug("rwpath  : %r" % path)
    if FS.exists(path) and FS.isdir(path):
        index_html = pathjoin(path, 'index.html')
        if FS.exists(index_html) and FS.isfile(index_html):
            path = index_html
        else:
            if request.app.config.get('pgs.show_dirlists'):
                return list(generate_dirlist_html(FS, path))
                # TODO: mtime ?

    if isinstance(FS, DirectoryRepositoryFS):
        return bottle.static_file(path, root=app.config['pgs.root_path'])
    elif isinstance(FS, SubprocessGitRepositoryFS):
        # this is mostly derived from bottle.static_file
        # without the RANGE support
        return git_static_file(path)
    else:
        raise Exception(FS, type(FS))


def git_static_file(filename,
                    mimetype='auto',
                    download=False,
                    charset='UTF-8'):
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

    clen
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
    if config_obj.root_path:
        app.config['pgs.root_path'] = os.path.abspath(
            os.path.expanduser(config_obj.root_path))
    if config_obj.git_repo_path:
        app.config['pgs.git_repo_path'] = os.path.abspath(
            os.path.expanduser(config_obj.git_repo_path))
        app.config['pgs.git_repo_rev'] = config_obj.git_repo_rev

    log.info("app.config: %s" % app.config)
    app = configure_app(app)
    return bottle.run(app,
                      host=config_obj.host,
                      port=config_obj.port,
                      debug=config_obj.debug,
                      reloader=config_obj.reloader)


def main(argv=1j):
    import logging
    import optparse
    import sys

    prs = optparse.OptionParser(
        usage="%prog [-p <path>] [-g <repopath>] [-r <rev/tag/branch>]",
        description="Serve a directory or a git revision over HTTP "
                    "with Bottle, WSGI, MIME types, and Last-Modified headers")

    prs.add_option('-p', '--path', '--prefix',
                   dest='root_path',
                   help='Filesystem path to serve files from')

    prs.add_option('-g', '--git',
                   dest='git_repo_path',
                   help='Path to git repo to serve files from')
    prs.add_option('-r', '--rev',
                   dest='git_repo_rev',
                   help='Git repo revision (commit hash, branch, tag)',
                   default='gh-pages')

    prs.add_option('-H', '--host',
                   dest='host',
                   default='localhost')
    prs.add_option('-P', '--port',
                   dest='port',
                   default='8082')
    prs.add_option('--debug',
                   dest='debug',
                   default=True,
                   action='store_false',
                   help='set bottle debug=False')
    prs.add_option('--reload',
                   dest='reloader',
                   default=True,
                   action='store_false',
                   help='set bottle reload=False')

    prs.add_option('-v', '--verbose',
                   dest='verbose',
                   action='store_true',)
    prs.add_option('-q', '--quiet',
                   dest='quiet',
                   action='store_true',)
    prs.add_option('-t', '--test',
                   dest='run_tests',
                   action='store_true',)
    _argv = []
    if argv == 1j:
        _argv = sys.argv[1:]
    elif argv is None:
        _argv = []
    (opts, args) = prs.parse_args(args=_argv)  # _argv)

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
        return unittest.main(argv=__argv)

    output = pgs(app, opts)
    output
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main(argv=1j))
