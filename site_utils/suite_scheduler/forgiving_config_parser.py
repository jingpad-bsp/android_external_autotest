# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import ConfigParser


def forgive_config_error(func):
    """A decorator to make ConfigParser get*() functions return None on fail."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ConfigParser.Error:
            return None
    return wrapper


class ForgivingConfigParser(ConfigParser.SafeConfigParser):
    """A SafeConfigParser that returns None on any error in get*().

    Note that I can't use super() here, as ConfigParser.SafeConfigParser
    isn't a new-style class.
    """


    @forgive_config_error
    def getstring(self, section, option):
        """Can't override get(), as it breaks the other getters to have get()
        return None sometimes."""
        return ConfigParser.SafeConfigParser.get(self, section, option)


    @forgive_config_error
    def getint(self, section, option):
        return ConfigParser.SafeConfigParser.getint(self, section, option)


    @forgive_config_error
    def getfloat(self, section, option):
        return ConfigParser.SafeConfigParser.getfloat(self, section, option)


    @forgive_config_error
    def getboolean(self, section, option):
        return ConfigParser.SafeConfigParser.getboolean(self, section, option)
