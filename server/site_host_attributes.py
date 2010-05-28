# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, utils

# Host attributes are specified a strings with the format:
#   <key>{,<value>}?
#
# A machine may have a list of strings for attributes like:
#
#   ['has_80211n,True',
#    'has_ssd,False',
#    'drive_kind,string,ssd,1']
#
# A legal attribute has the pattern:
#   <name>,<kind>(,<extra>)?
#
# Name can be any legal python identifier.  Kind may be any of 'string',
# 'True', or 'False'.  Only if kind is string can there be extra data.
#
# Strings which are not legal attributes are ignored.
#
# Given the above list of attributes, you can use the syntax:
#   host_attributes.drive_kind => 'ssd,1'
#   host_attributes.has_80211n => True
#   host_attributes.has_ssd => False
#   host_attributes.unknown_attribute => raise KeyError
#
# Machine attributes can be specified in two ways.
#
# If you create private_host_attributes_config.py and
# private_host_attributes there, we will use it when possible instead of
# using the server front-end.
#
# Example configuration:
#   private_host_attributes = {
#     "myserver": ["has_80211n,True",
#                  "has_resume_bug,False"]
#   }
#
# We also consult the AFE database for its labels which are all treated
# as host attribute strings defined above.  Illegal strings are ignored.
#

private_host_attributes = utils.import_site_symbol(
    __file__,
    'autotest_lib.server.private_host_attributes_config',
    'private_host_attributes', dummy={})

try:
    settings = 'autotest_lib.frontend.settings'
    os.environ['DJANGO_SETTINGS_MODULE'] = settings
    from autotest_lib.frontend.afe import models
    has_models = True
except ImportError, e:
    has_models = False


_DEFAULT_ATTRIBUTES = [
    'has_80211n,True',
    'has_bluetooth,True',
    'has_chromeos_firmware,False',
    'has_resume_bug,False',
    'has_ssd,True',
    ]


class HostAttributes(object):


    def __init__(self, host):
        """
        Create an instance of HostAttribute for the given hostname.
        We look up the host in both the hardcoded configuration and
        the AFE models if they can be found.
        """
        self._add_attributes(_DEFAULT_ATTRIBUTES)
        if host in private_host_attributes:
            self._add_attributes(private_host_attributes[host])
        if has_models:
            host_obj = models.Host.valid_objects.get(hostname=host)
            self._add_attributes([label.name for label in
                                  host_obj.labels.all()])
        for key, value in self.__dict__.items():
            logging.info('Host attribute: %s => %s', key, value)


    def _add_attributes(self, attributes):
        for attribute in attributes:
            splitnames = attribute.split(',')
            value = ','.join(splitnames[1:])
            if len(splitnames) == 1:
                continue
            if value == 'True':
                value = True
            elif value == 'False':
                value = False
            elif splitnames[1] == 'string':
                logging.info('Non-attribute string "%s" is ignored' % attribute)
                continue
            setattr(self, splitnames[0], value)
