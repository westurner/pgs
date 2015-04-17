#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_pgs
----------------------------------

Tests for `pgs` module.
"""

import unittest

import collections
import os.path

import pgs.app
from pgs.app import pathjoin

CUR_DIR = os.path.dirname(os.path.abspath(__file__))

ROOT_PATH = os.path.abspath(os.path.join(CUR_DIR, '..'))
TEST_WWW_DIR = os.path.join(CUR_DIR, 'www')

GIT_REPO_PATH = ROOT_PATH
GIT_REPO_REV = 'pgs-test'

confs = collections.OrderedDict()
confs['fs0'] = {
    'pgs.root_path': TEST_WWW_DIR
}
confs['git0'] = {
    'pgs.git_repo_path': GIT_REPO_PATH,
    'pgs.git_repo_rev': 'pgs-test'
}


class TestPathJoin(unittest.TestCase):

    def test_pathjoin_01(self):
        output = pathjoin('/a', '/g')
        self.assertEqual(output, '/a/g')
        output = pathjoin('/a', 'g')
        self.assertEqual(output, '/a/g')
        output = pathjoin('/a/', 'g')
        self.assertEqual(output, '/a/g')
        output = pathjoin('a', 'g')
        self.assertEqual(output, 'a/g')
        output = pathjoin('a', '/g')
        self.assertEqual(output, 'a/g')
        output = pathjoin('a', 'g/')
        self.assertEqual(output, 'a/g/')
        output = pathjoin('a', '/g/')
        self.assertEqual(output, 'a/g/')
        output = pathjoin('/a/', '/g/')
        self.assertEqual(output, '/a/g/')
        output = pathjoin('/a/b/c/', '/1/2/3/', 'd/e/f/', '/4/5/6/')
        self.assertEqual(output, '/a/b/c/1/2/3/d/e/f/4/5/6/')

        output = pathjoin('')
        self.assertEqual(output, '')
        output = pathjoin('', '/')
        self.assertEqual(output, '/')
        output = pathjoin('', '/index.html')
        self.assertEqual(output, '/index.html')

        output = pathjoin('/a/b', 'index.html')
        self.assertEqual(output, '/a/b/index.html')


class FSTestUtils(object):

    @staticmethod
    def _test_fs_dir(self, fs, _path, conf):
        ROOT_PATH = conf.get('pgs.root_path')
        self.assertTrue(fs)

        path = fs.getsyspath(_path)
        self.assertTrue(path)
        if ROOT_PATH:
            self.assertEqual(path, pathjoin(ROOT_PATH, _path))
        else:
            self.assertEqual(path, _path)

        exists = fs.exists(_path)
        self.assertTrue(exists, "%r.exist == False" % _path)
        isdir = fs.isdir(_path)
        self.assertTrue(isdir)
        isfile = fs.isfile(_path)
        self.assertFalse(isfile)

        info = fs.getinfo(_path)
        self.assertTrue(info)
        for key in ['size', 'created_time', 'modified_time', 'accessed_time']:
            self.assertIn(key, info)
            self.assertTrue(info[key])

        if ROOT_PATH:
            _stat = os.stat(path)
            self.assertEqual(info['size'], _stat.st_size)
            self.assertEqual(info['created_time'], _stat.st_ctime)
            self.assertEqual(info['modified_time'], _stat.st_mtime)
            self.assertEqual(info['accessed_time'], _stat.st_atime)

        output = fs.listdir(_path)
        self.assertTrue(output)

        output = fs.listdirinfo(_path)
        self.assertTrue(output)

    @staticmethod
    def _test_getsyspath(self, _path):
        path = self.fs.getsyspath(_path)
        self.assertTrue(path)
        self.assertEqual(path, pathjoin(ROOT_PATH, _path))

    @staticmethod
    def _test_fs_file(self, fs, _path, conf):
        ROOT_PATH = conf.get('pgs.root_path')
        self.assertTrue(fs)

        path = fs.getsyspath(_path)
        self.assertTrue(path)
        if ROOT_PATH:
            self.assertEqual(path, pathjoin(ROOT_PATH, _path))
            _exists = os.path.exists(path)
            self.assertTrue(_exists, "%r.os.path.exists == False" % path)
        else:
            self.assertEqual(path, _path)

        exists = fs.exists(_path)
        self.assertTrue(exists, (_path, path))
        isdir = fs.isdir(_path)
        self.assertFalse(isdir)
        isfile = fs.isfile(_path)
        self.assertTrue(isfile)

        info = fs.getinfo(_path)
        self.assertTrue(info)
        for key in ['size', 'created_time', 'modified_time', 'accessed_time']:
            self.assertIn(key, info)
            self.assertTrue(info[key])

        if ROOT_PATH:
            _stat = os.stat(path)
            self.assertEqual(info['size'], _stat.st_size)
            self.assertEqual(info['created_time'], _stat.st_ctime)
            self.assertEqual(info['modified_time'], _stat.st_mtime)
            self.assertEqual(info['accessed_time'], _stat.st_atime)

        fileobj = fs.get_fileobj(_path)
        self.assertTrue(fileobj)
        self.assertTrue(hasattr(fileobj, '__iter__'))
        self.assertTrue(hasattr(fileobj, 'read'))
        contents = fileobj.read()
        self.assertTrue(contents)

        fileobj = fs.get_fileobj(_path)
        self.assertTrue(fileobj)
        self.assertTrue(hasattr(fileobj, '__iter__'))
        self.assertTrue(hasattr(fileobj, 'read'))
        contents = []
        for line in fileobj:
            contents.append(line)
        self.assertTrue(contents)


class TestDirectoryRepositoryFS(unittest.TestCase, FSTestUtils):

    dirs = ['/', '/a', '/a/']
    files = ['/index.html', 'index.html', 'a/b/c']

    Class = pgs.app.DirectoryRepositoryFS
    conf = confs['fs0']

    def setUp(self):
        self.FS = self.Class(self.conf)

    def test_010_root_dir(self):
        return self._test_fs_dir(self, self.FS, '/', self.conf)

    def test_020_dirs(self):
        for dirpath in self.dirs:
            self._test_fs_dir(self, self.FS, dirpath, self.conf)

    def test_050_index_html(self):
        return self._test_fs_file(self, self.FS, 'index.html', self.conf)

    def test_060(self):
        for _path in self.files:
            return self._test_fs_file(self, self.FS, _path, self.conf)


class TestSubprocessGitRepositoryFS(TestDirectoryRepositoryFS):
    Class = pgs.app.SubprocessGitRepositoryFS
    conf = {'pgs.git_repo_path': GIT_REPO_PATH,
            'pgs.git_repo_rev': 'pgs-test'}


class TestPgsApp(unittest.TestCase):

    def setUp(self):
        pass

    def test_make_app(self):
        app = pgs.app.make_app()
        self.assertTrue(app)

    def test_make_app_FS(self):
        conf = confs['fs0']
        app = pgs.app.make_app(conf=conf)
        self.assertTrue(app)
        for key in conf:
            self.assertEqual(app.config[key], conf[key])
        self.assertIn('pgs.FS', app.config)
        fs = app.config.get('pgs.FS')
        self.assertTrue(fs)

    def test_make_app_git(self):
        conf = confs['git0']
        app = pgs.app.make_app(conf)
        self.assertTrue(app)
        for key in conf:
            self.assertEqual(app.config[key], conf[key])
        self.assertIn('pgs.FS', app.config)
        fs = app.config.get('pgs.FS')
        self.assertTrue(fs)


# WebTest WSGI tests

import webtest


class TestWebPgs_SubprocessGitRepositoryFS(unittest.TestCase):

    conf = confs['git0']

    def setUp(self):
        app = pgs.app.configure_app(pgs.app.app, self.conf)
        self.app = webtest.TestApp(app)

    def test_root(self):
        for url in ['/', '/index.html', '/index']:
            rsp = self.app.get(url)
            self.assertEqual(rsp.text, u'awesome\n')

    def test_abc(self):
        for url in ['/a/b/', '/a/b/index.html', '/a/b/index', '/a/b']:
            rsp = self.app.get(url)
            self.assertEqual(rsp.text, u'here\n')

    def test_dirlists(self):
        for url in ['/a',
                    '/@@', '/a/@@', '/a/b/@@', '/a@@']:
            rsp = self.app.get(url)
            rsp.mustcontain(u'class="dirlist"')


class TestWebPgs_DirectoryRepositoryFS(TestWebPgs_SubprocessGitRepositoryFS):

    conf = confs['fs0']


if __name__ == '__main__':
    unittest.main()
