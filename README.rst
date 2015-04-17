===============================
pgs
===============================

.. .. image:: https://img.shields.io/travis/westurner/pgs.svg
..         :target: https://travis-ci.org/westurner/pgs

.. .. image:: https://img.shields.io/pypi/v/pgs.svg
..        :target: https://pypi.python.org/pypi/pgs

A bottle webapp for serving static files from a git branch,
or from the local filesystem.

* Free software: MIT license
* Source: https://github.com/westurner/pgs


Features
--------

* [x] Serve static files from a filesystem directory
* [x] Serve static files from a git branch,
  with Last-Modified headers according to git timestamps
* [x] Guess MIME-types from paths
* [x] subprocess bindings to ``git cat-file`` and ``git show``
* [ ] dulwich
* [ ] pygit2


Usage
------

Serve ``/var/www/html`` from http://localhost:8082/

.. code:: bash

   pgs -p /var/www/html

Serve the ``gh-pages`` branch of this repo from http://localhost:8083

.. code:: bash

   pgs -g $VIRTUAL_ENV/src/pgs -r gh-pages -P 8083


Further Usage:

.. code:: bash

    $ pgs --help
    Usage: pgs [-p <path>] [-g <repopath>] [-r <rev/tag/branch>]

    Serve a directory or a git revision over HTTP with Bottle, WSGI, MIME types,
    and Last-Modified headers

    Options:
      -h, --help            show this help message and exit
      -p ROOT_FILEPATH, --path=ROOT_FILEPATH, --root_filepath=ROOT_FILEPATH
      -g GIT_REPO_PATH, --git=GIT_REPO_PATH
                            Path to git repo to serve files from
      -r GIT_REPO_REV, --rev=GIT_REPO_REV
                            Git repo revision (commit hash, branch, tag)
      -H HOST, --host=HOST  
      -P PORT, --port=PORT  
      --debug               set bottle debug=False
      --reload              set bottle reload=False
      -v, --verbose         
      -q, --quiet           
      -t, --test


Caveat Emptor
---------------
* Upstream caching would be necessary for all but the most local use
  cases
* True git bindings would likely do less buffering of
  ``subprocess.check_output``
