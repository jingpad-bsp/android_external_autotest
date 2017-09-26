# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Kludges to support legacy Autotest code.

Autotest imports should be done by calling monkeypatch() first and then
calling load().  monkeypatch() should only be called once from a
script's main function.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import imp
import importlib
import logging
import os
import site
import sys

import autotest_lib

_AUTOTEST_DIR = autotest_lib.__path__[0]
_SITEPKG_DIR = os.path.join(_AUTOTEST_DIR, 'site-packages')

_setup_done = False

logger = logging.getLogger(__name__)


def monkeypatch():
    """Do necessary Autotest monkeypatching.

    This should be called before any autotest_lib imports in the main
    function in scripts.  Thus, only the main function in scripts can
    import autotest_lib.

    Library code should rely on dependency injection, falling back to
    load().

    This should be called no more than once.

    This adds Autotest's site-packages and modifies sys.meta_path so
    that all common.py imports are no-ops.
    """
    global _setup_done
    assert not _setup_done
    site.addsitedir(_SITEPKG_DIR)
    sys.meta_path.insert(0, _CommonRemovingFinder())
    _setup_done = True


class _CommonRemovingFinder(object):
    """Python import finder that neuters Autotest's common.py

    The common module is replaced with an empty module everywhere it is
    imported.  common.py should have only been imported for side
    effects, so nothing should actually use the imported module.

    See also https://www.python.org/dev/peps/pep-0302/
    """

    def find_module(self, fullname, path=None):
        """Find module."""
        del path  # unused
        if not self._is_autotest_common(fullname):
            return None
        logger.debug('Dummying out %s import', fullname)
        return self

    def _is_autotest_common(self, fullname):
        return (fullname.partition('.')[0] == 'autotest_lib'
                and fullname.rpartition('.')[-1] == 'common')

    def load_module(self, fullname):
        """Load module."""
        if fullname in sys.modules:
            return sys.modules[fullname]
        mod = imp.new_module(fullname)
        mod.__file__ = '<removed>'
        mod.__loader__ = self
        mod.__package__ = fullname.rpartition('.')[0]
        sys.modules[fullname] = mod
        return mod


def load(name):
    """Import module from autotest.

    This enforces that monkeypatch() is called first.  Otherwise,
    autotest imports may or may not work.  When they do work, they may
    screw up global state.

    @param name: name of module as string, e.g., 'frontend.afe.models'
    """
    if not _setup_done:
        raise ImportError('cannot load Autotest modules before monkeypatching')
    relpath = name.lstrip('.')
    return importlib.import_module('.%s' % relpath, package='autotest_lib')
