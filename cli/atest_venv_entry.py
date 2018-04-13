#!/usr/bin/python -u
import os
import sys

import common
from autotest_lib.cli import atest

_AUTOTEST_ROOT = os.path.realpath(os.path.join(__file__, '..', '..'))
_CHROMIUMOS_ROOT = os.path.abspath(
    os.path.join(_AUTOTEST_ROOT, '..', '..', '..', '..'))
_SKYLAB_INVENTORY_DIR = os.path.join(_CHROMIUMOS_ROOT, 'infra',
                                     'skylab_inventory', 'venv')
# In any sane chromiumos checkout
sys.path.append(_SKYLAB_INVENTORY_DIR)
# TODO: Where is this checked out on infra servers?

try:
  import skylab_inventory  # pylint: disable=unused-import
except ImportError as e:
  raise Exception('Error when importing skylab_inventory (venv dir: %s): %s'
                  % (_SKYLAB_INVENTORY_DIR, e))


sys.exit(atest.main())
