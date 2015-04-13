#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function
"""
pygitpages.app
===============

Objectives:

* Learn Bottle
* Serve Static Files (such as ``index.html``)
* Append .html (``file_path = URL + '.html'``)

"""
import cgi
import collections
import codecs
import distutils.spawn
import mimetypes
import os.path
import subprocess
import time
import urlparse


import bottle
# from bottle import Bottle, route, run, request, static_file
from bottle import parse_date, request, HTTPResponse, HTTPError
try:
    import dulwich
except ImportError:
    dulwich = None


class DirectoryRepositoryFS(object):

    def __init__(self, *args, **kwargs):
        self.root_filepath = kwargs['root_filepath']

    def exists(self, path):
        return os.path.exists(path)

    def isdir(self, path):
        return os.path.isdir(path)

    def isfile(self, path):
        return os.path.isfile(path)

    def listdir(self, path, **kwargs):
        if kwargs:
            raise NotImplementedError()  # ~-> PyFilesystem interface
        return os.listdir(path)

    def listdirinfo(self, path, **kwargs):
        if kwargs:
            raise NotImplementedError()  # ~-> PyFilesystem interface
        return [self.getinfo(p) for p in self.listdir(path, **kwargs)]

    def get_contents(self, path, *args, **kwargs):
        kwargs.setdefault('encoding', 'UTF-8')
        with codecs.open(path, *args, **kwargs) as f:
            return f  # .read()  # XXX

    def getsyspath(self, path, allow_none=False):
        return os.path.join(self.root_filepath, path)

    def hassyspath(self, path):
        return bool(self.getsyspath(path))


class SubprocessGitRepositoryFS(object):

    GIT_BIN = distutils.spawn.find_executable('git')

    def __init__(self, path, rev=None):
        self.repo_path = path
        self.repo_rev = rev or 'HEAD'

    def git_cmd(self):
        return [self.GIT_BIN, '-C', self.repo_path]

    def to_git_pathspec(self, path):
        return "%s:%s" % (self.repo_rev, path)

    def exists(self, path):
        cmd = self.git_cmd() + ['cat-file', '-e', self.to_git_pathspec(path)]
        retcode = subprocess.call(cmd, stderr=subprocess.STDOUT)
        return retcode == 0

    def getsize(self, path):
        cmd = self.git_cmd() + ['cat-file', '-s', self.to_git_pathspec(path)]
        return long(subprocess.check_output(cmd))

    def get_author_committer_dates(self, path):
        cmd = self.git_cmd() + ['log', '-1', "--format=%at %ct",
                                self.repo_rev,
                                '--', path]
        output = subprocess.check_output(cmd)
        author_date, committer_date = output.rstrip().split()
        return int(author_date), int(committer_date)

    def getinfo(self, path):
        attrs = collections.OrderedDict()
        attrs["size"] = self.getsize(path)
        _, committer_date = self.get_author_committer_dates(path)
        attrs["created_time"] = committer_date
        attrs["accessed_time"] = committer_date
        attrs["modified_time"] = committer_date
        return attrs

    def get_object_type(self, path):
        cmd = self.git_cmd() + ['cat-file', '-t', self.to_git_pathspec(path)]
        return subprocess.check_output(cmd).strip()

    def isdir(self, path):
        return self.get_object_type(path) == 'tree'

    def isfile(self, path):
        return self.get_object_type(path) == 'blob'

    def listdir(self, path, **kwargs):
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
        return [self.getinfo(p) for p in self.listdir(path, **kwargs)]

    def get_contents(self, path):
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


# bottle app

def make_app():
    app = bottle.Bottle()
    app.config['root_filepath'] = os.path.abspath('.')
    app.config['show_directory_listings'] = True

    app.config['FS'] = DirectoryRepositoryFS(
        root_filepath=app.config['root_filepath'])

    return app


app = make_app()


@app.hook('config')
def on_config_change(key, value):
    if key == 'root_filepath':
        if value:
            app.config['FS'] = DirectoryRepositoryFS(
                root_filepath=app.config['root_filepath'])
    elif key in ('git_repo_path', 'git_repo_rev'):
        if value:
            app.config['FS'] = SubprocessGitRepositoryFS(
                app.config['git_repo_path'],
                app.config.get('git_repo_rev', 'gh-pages'))


def sanitize_path(path):
    # XXX TODO FIXME
    if '/../' in path:
        raise Exception()
    return path


def rewrite_path(_path, root_filepath):
    """

    Args:
        _path (str): path to rewrite (in search of index.html)
        root_filepath (str): filesystem root_filepath

    """
    FS = app.config['FS']
    path = sanitize_path(_path)
    full_path = FS.getsyspath(path)
    if FS.exists(full_path):
        if FS.isdir(full_path):
            dir_index_html_path = os.path.join(full_path, 'index.html')
            if FS.exists(dir_index_html_path) and FS.isfile(dir_index_html_path):
                return urlparse.urljoin(path, 'index.html')
        return path
    else:
        # try appending '.html'
        if not (path.endswith('/') or path.endswith('.html')):
            path_dot_html = path + ".html"
            disk_path = FS.getsyspath(path_dot_html)
            if FS.exists(disk_path) and FS.isfile(disk_path):
                return path_dot_html
        return path


@app.route('/')
def serve_index_html():
    FS = request.app.config['FS']
    if isinstance(FS, DirectoryRepositoryFS):
        return bottle.static_file('index.html',
                                  root=app.config['root_filepath'])
    else:
        return git_static_file('index.html'), # TODO


def generate_listdir_html_table(filepath, root_filepath):
    """
    Generate directory listing HTML

    Arguments:
        filepath (str):
        root_filepath (str):

    Keyword Arguments:
        list_dir (callable: list[str]): list file names in a directory
        isdir (callable: bool): os.path.isdir

    Yields:
        str: lines of an HTML table
    """
    FS = app.config['FS']
    yield '<table>'
    if filepath == '/':
        filepath = ''
    if isinstance(FS, DirectoryRepositoryFS):
        dir_path = os.path.join(root_filepath, filepath)
    else:
        dir_path = filepath
    # print("ROOT_FILEPATH: %r" % root_filepath)
    # print("FILEPATH: %r" % filepath)
    # print("dir_path: %r" % dir_path)
    for name in FS.listdir(dir_path):
        full_path = os.path.join(dir_path, name)
        absolute_url = u'/'.join(('', filepath.rstrip('/'), name))
        if FS.isdir(full_path):
            absolute_url = absolute_url + '/'
        yield u'<tr><td><a href="{0}">{0}</a></td></tr>'.format(
            cgi.escape(absolute_url))  # TODO XXX
    yield '</table>'


@app.route('/<filepath:path>@@')
def serve_directory_listing(filepath):
    FS = request.app.config['FS']
    root_filepath = app.config['root_filepath']
    full_path = FS.getsyspath(filepath)
    if FS.exists(full_path) and FS.isdir(full_path):
        if app.config.get('show_directory_listings'):
            return list(generate_listdir_html_table(filepath, root_filepath))


@app.route('/<filepath:path>')
def serve_static_files(filepath):
    FS = request.app.config['FS']
    root_filepath = app.config['root_filepath']
    if filepath == '':
        filepath = 'index.html'
    else:
        filepath = rewrite_path(filepath, root_filepath)  # or ''  # XXX
    full_path = FS.getsyspath(filepath)
    if FS.exists(full_path) and FS.isdir(full_path):
        index_html = os.path.join(full_path, 'index.html')
        if FS.exists(index_html) and FS.isfile(index_html):
            filepath = index_html
        if app.config.get('show_directory_listings'):
            return list(generate_listdir_html_table(filepath, root_filepath))

    if isinstance(FS, DirectoryRepositoryFS):
        return bottle.static_file(filepath, root=root_filepath)
    else:
        # this is mostly derived from bottle.static_file
        # without the RANGE support
        return git_static_file(filepath)
        import mimetypes
        body = FS.get_contents(filepath)  # XXX
        mime_guess, encoding = mimetypes.guess_type(filepath)
        if mime_guess.startswith('text'):
            mime_guess = "%s ; charset: UTF-8" % mime_guess
        headers = dict()
        if encoding:
            headers['Content-Encoding'] = encoding
        headers['Content-Length'] = len(body)
        headers['Content-Type'] = mime_guess

        return bottle.HTTPResponse(body, **headers)


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

    #root = os.path.abspath(root) + os.sep
    #filename = os.path.abspath(os.path.join(root, filename.strip('/\\')))
    filename = filename.strip('/\\')
    headers = dict()

    FS = request.app.config['FS']
    #if not filename.startswith(root):
    #    return HTTPError(403, "Access denied.")
    if not FS.exists(filename):
        return HTTPError(404, "Not found.")
    #if not os.access(filename, os.R_OK):
    #    return HTTPError(403, "You do not have permission to access this file.")

    if mimetype == 'auto':
        if download and download != True:
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

    body = '' if request.method == 'HEAD' else FS.get_contents(filename)

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


def pygitpages(app, config_obj):
    app.config['root_filepath'] = os.path.abspath(
        os.path.expanduser(config_obj.root_filepath))

    if config_obj.git_repo_path:
        app.config['FS'] = SubprocessGitRepositoryFS(config_obj.git_repo_path,
                                                     config_obj.git_repo_rev)
    print("app.config: %s" % app.config)
    return bottle.run(app,
                      host=config_obj.host,
                      port=config_obj.port,
                      debug=config_obj.debug,
                      reloader=config_obj.reloader)


import unittest


class Test_pygitpages(unittest.TestCase):

    def test_pygitpages(self):
        app = make_app()
        self.assertTrue(app)


def main():
    import logging
    import optparse
    import sys

    prs = optparse.OptionParser(
        usage="%prog [-p <root_filepath>]",
        description="Serve a directory or a git revision over HTTP with bottle")

    prs.add_option('-p', '--path', '--root_filepath',
                   dest='root_filepath',
                   default='.')

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

    (opts, args) = prs.parse_args()

    if not opts.quiet:
        logging.basicConfig()

        if opts.verbose:
            logging.getLogger().setLevel(logging.DEBUG)

    if opts.run_tests:
        sys.argv = [sys.argv[0]] + args
        import unittest
        exit(unittest.main())

    output = pygitpages(app, opts)
    output
    sys.exit(0)


if __name__ == "__main__":
    main()
