# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# DESCRIPTION :
#
# This library provides mocked exception classes that replace all newline
# characters with "<br/>" so that the factory log is easier to parse.

from autotest_lib.client.common_lib import error

_glob = globals()
for _name in error.__all__:
    _thing = error.__dict__[_name]
    if isinstance(_thing, type) and issubclass(_thing, Exception):
        _str = lambda self: _thing.__str__(self).replace('\n', '<br/>')
        _glob[_name] = type(_name, (_thing,), dict(__str__=_str))
    else:
        _glob[_name] = _thing

__all__ = error.__all__
