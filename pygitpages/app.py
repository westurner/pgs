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

import cgi
import os.path
import urlparse

def build_bottle_app():
    app = bottle.Bottle()
    app.config['root_filepath'] = os.path.abspath('.')
    app.config['show_directory_listings'] = True
    return app


app = build_bottle_app()


def sanitize_path(path):
    # XXX TODO FIXME
    if '/../' in path:
        raise Exception()
    return path


def rewrite_path(_path, root_filepath,
                 exists=os.path.exists,
                 is_dir=os.path.isdir,
                 is_file=os.path.isfile):
    """

    Args:
        _path (str): path to rewrite (in search of index.html)
        root_filepath (str): filesystem root_filepath

    """
    path = sanitize_path(_path)
    full_path = os.path.join(root_filepath, path)
    if exists(full_path):
        if is_dir(full_path):
            dir_index_html_path = os.path.join(full_path, 'index.html')
            if exists(dir_index_html_path) and is_file(dir_index_html_path):
                return urlparse.urljoin(path, 'index.html')
        return path
    else:
        # try appending '.html'
        if not (path.endswith('/') or path.endswith('.html')):
            path_dot_html = path + ".html"
            disk_path = os.path.join(root_filepath, path_dot_html)
            if exists(disk_path) and is_file(disk_path):
                return path_dot_html
        return path


@app.route('/')
def serve_index_html():
    return bottle.static_file('index.html', root=app.config['root_filepath'])


def generate_listdir_html_table(filepath, root_filepath,
                                list_dir=os.listdir,
                                is_dir=os.path.isdir):
    """
    Generate directory listing HTML

    Arguments:
        filepath (str):
        root_filepath (str):

    Keyword Arguments:
        list_dir (callable: list[str]): list file names in a directory
        is_dir (callable: bool): os.path.isdir

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
    for name in list_dir(dir_path):
        full_path = os.path.join(dir_path, name)
        absolute_url = u'/'.join(('', filepath, name))
        if is_dir(full_path):
            absolute_url = absolute_url + '/'
        yield u'<tr><td><a href="{0}">{0}</a></td></tr>'.format(
            cgi.escape(absolute_url))  # TODO XXX
    yield '</table>'


@app.route('/<filepath:path>')
def serve_static_files(filepath,
                       exists=os.path.exists,
                       is_dir=os.path.isdir,
                       is_file=os.path.isfile):
    root_filepath = app.config['root_filepath']
    if filepath == '':
        filepath = 'index.html'
    else:
        filepath = rewrite_path(filepath, root_filepath)  # or ''  # XXX
    full_path = os.path.join(root_filepath, filepath)
    if exists(full_path) and is_dir(full_path):
        index_html = os.path.join(full_path, 'index.html')
        if exists(index_html) and is_file(index_html):
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
