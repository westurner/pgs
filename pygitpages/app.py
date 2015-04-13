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
import bottle
# from bottle import Bottle, route, run, request, static_file

import codecs
import cgi
import os.path
import subprocess
import urlparse

try:
    import dulwich
except ImportError:
    dulwich = None

def build_bottle_app():
    app = bottle.Bottle()
    app.config['root_filepath'] = os.path.abspath('.')
    app.config['show_directory_listings'] = True
    return app


app = build_bottle_app()

class DirectoryRepositoryFS(object):

    def __init__(self, *args, **kwargs):
        pass

    def exists(self, path):
        return os.path.exists(path)

    def isdir(self, path):
        return os.path.isdir(path)

    def isfile(self, path):
        return os.path.isfile(path)

    def listdir(self, path):
        return os.listdir(path)

    def read_contents(self, path, *args, **kwargs):
        with codecs.open(path, *args, **kwargs) as f:
            return f.read()  # XXX


class SubprocessGitRepositoryFS(object):

    def __init__(self, repo_path, rev=None):
        self.repo_path = repo_path
        self.rev = rev or 'HEAD'

    @property
    def git_cmd(self):
        return ['git', '-R', self.repo_path]

    def to_git_pathspec(self, path):
        return "%s:%s" % (self.rev, path)

    def exists(self, path):
        cmd = self.git_cmd() + ['cat-file', '-e', self.to_git_pathspec(path)]
        retcode = subprocess.call(cmd)
        return retcode == 0

    def get_object_type(self, path):
        cmd = self.git_cmd() + ['cat-file', '-t', self.to_git_pathspec(path)]
        return subprocess.check_output(cmd).strip()

    def isdir(self, path):
        return self.get_object_type(path) == 'tree'

    def isfile(self, path):
        return self.get_object_type(path) == 'blob'

    def listdir(self, path):
        cmd = self.git_cmd() + ['cat-file', '-p', self.to_git_pathspec(path)]
        output = subprocess.checkoutput(cmd)
        files = []
        for _line in output.splitlines():
            line = _line.strip()
            if line:
                perms, type_, hash, name = line.split(None, 3)
                #yield (name)
                files.append(name)
        return files

    def read_contents(self, path):
        cmd = self.git_cmd() + ['show', self.to_git_pathspec(path)]
        return subprocess.check_output(cmd)



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



def sanitize_path(path):
    # XXX TODO FIXME
    if '/../' in path:
        raise Exception()
    return path

FS = DirectoryRepositoryFS()
#FS = SubprocessGitRepositoryFS(repo_path, rev)

def rewrite_path(_path, root_filepath):
    """

    Args:
        _path (str): path to rewrite (in search of index.html)
        root_filepath (str): filesystem root_filepath

    """
    path = sanitize_path(_path)
    full_path = os.path.join(root_filepath, path)
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
            disk_path = os.path.join(root_filepath, path_dot_html)
            if FS.exists(disk_path) and FS.isfile(disk_path):
                return path_dot_html
        return path


@app.route('/')
def serve_index_html():
    return bottle.static_file('index.html', root=app.config['root_filepath'])


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
    yield '<table>'
    if filepath == '/':
        filepath = ''
    dir_path = os.path.join(root_filepath, filepath)
    print("ROOT_FILEPATH: %r" % root_filepath)
    print("FILEPATH: %r" % filepath)
    print("dir_path: %r" % dir_path)
    for name in FS.listdir(dir_path):
        full_path = os.path.join(dir_path, name)
        absolute_url = u'/'.join(('', filepath, name))
        if FS.isdir(full_path):
            absolute_url = absolute_url + '/'
        yield u'<tr><td><a href="{0}">{0}</a></td></tr>'.format(
            cgi.escape(absolute_url))  # TODO XXX
    yield '</table>'


@app.route('/<filepath:path>')
def serve_static_files(filepath):
    root_filepath = app.config['root_filepath']
    if filepath == '':
        filepath = 'index.html'
    else:
        filepath = rewrite_path(filepath, root_filepath)  # or ''  # XXX
    full_path = os.path.join(root_filepath, filepath)
    if FS.exists(full_path) and FS.isdir(full_path):
        index_html = os.path.join(full_path, 'index.html')
        if FS.exists(index_html) and FS.isfile(index_html):
            filepath = index_html
        if app.config.get('show_directory_listings'):
            return list(generate_listdir_html_table(filepath, root_filepath))
        # str(os.listdir(full_path))
    return bottle.static_file(filepath, root=root_filepath)


def pygitpages(app, config_obj):
    app.config['root_filepath'] = os.path.abspath(
        os.path.expanduser(config_obj.root_filepath))
    print(app.config)
    return bottle.run(app,
                      host=config_obj.host,
                      port=config_obj.port,
                      debug=config_obj.debug,
                      reloader=config_obj.reloader)


import unittest


class Test_pygitpages(unittest.TestCase):

    def test_pygitpages(self):

        pass


def main():
    import logging
    import optparse
    import sys

    prs = optparse.OptionParser(
        usage="%prog [-p <root_filepath>]",
        description="Serve a filesystem over http with bottle")

    prs.add_option('-p', '--path', '--root_filepath',
                   dest='root_filepath',
                   default='.')
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
