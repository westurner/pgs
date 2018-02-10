History
---------


develop (2018-02-10 16:49:59 -0500)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

   git log --reverse --pretty=format:'* %s [%h]' v0.1.3..develop

* MRG: Merge tag 'v0.1.3' into develop \[587b2ae\]
* DOC: HISTORY.rst: git-changelog.py --develop \[141d436\]


v0.1.3 (2018-02-10 16:39:21 -0500)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

   git log --reverse --pretty=format:'* %s [%h]' v0.1.2..v0.1.3

* Merge tag 'v0.1.2' into develop \[f0d9ad0\]
* DOC: setup.py: BSD License -> MIT License \[7744a0a\]
* DOC: setup.py: description \[905ff64\]
* MRG: Merge branch 'master' of ssh://github.com/westurner/pgs into release/0.1.3 \[82f3ab9\]
* DOC: __init__.py, setup.py: v0.1.3, rm email \[3945696\]
* MRG: Merge branch 'release/0.1.3' \[c8b3b9e\]


v0.1.2 (2015-04-17 08:26:35 -0500)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

   git log --reverse --pretty=format:'* %s [%h]' v0.1.1..v0.1.2

* BLD: requirements.txt: comment out bottle requirement \[e1416df\]
* BLD: setup.py: codecs.open(encoding='UTF8') \[75edc38\]
* TST: tests/www \[b332875\]
* BUG,TST,REF: unit tests, WebTest WSGI tests \[f08480d\]
* RLS: setup.py, __init__.py: version=0.1.2 \[2edc3a4\]
* Merge branch 'release/0.1.2' \[0bf19d3\]


v0.1.1 (2015-04-16 19:45:18 -0500)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

   git log --reverse --pretty=format:'* %s [%h]' 148d848..v0.1.1

* BLD: app.py, bottle.py: import bottle.py, static files w/ try files .html \[eed09fc\]
* TODO: ENH: add \*FS objects \[e80d75e\]
* ENH: app.py: host a git branch/revision/tag over HTTP \[3487e53\]
* Initial commit \[f124283\]
* Merge branch 'master' of ssh://github.com/westurner/pygitpages \[69b278c\]
* DOC,CLN: pygitpages.py/app.py \[552017e\]
* BLD: cookiecutter gh:audreyr/cookiecutter-pypackage <pgs> \[d791e95\]
* Merge pgs cookiecutter \[13edcb9\]
* REF: pygitpages/app.py, bottle.py -> pgs/ \[1f9ce1d\]
* CLN: rm pygitpages/ \[2ab456e\]
* DOC: app.py: pgs, description \[d4d46af\]
* BLD: requirements.txt: add 'bottle' (though it is also vendored) \[c224ef1\]
* BLD: setup.py: add pgs console_script entry_point to pgs.app:main \[01848bd\]
* REF: pygitpages -> pgs \[1a781af\]
* DOC: README.rst, app.py: usage, features \[259bd0c\]
* DOC: README.rst: RST formatting \[8beee37\]
* DOC: README.rst: Caveat Emptor \[ec590d1\]
