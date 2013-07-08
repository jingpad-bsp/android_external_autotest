# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import logging
import re

from autotest_lib.client.common_lib import base_utils, global_config
from autotest_lib.server.cros.dynamic_suite import constants


_SHERIFF_JS = global_config.global_config.get_config_value(
    'NOTIFICATIONS', 'sheriffs', default='')
_CHROMIUM_BUILD_URL = global_config.global_config.get_config_value(
    'NOTIFICATIONS', 'chromium_build_url', default='')


def get_label_from_afe(hostname, label_prefix, afe):
    """Retrieve a host's specific label from the AFE.

    Looks for a host label that has the form <label_prefix>:<value>
    and returns the "<value>" part of the label. None is returned
    if there is not a label matching the pattern

    @param hostname: hostname of given DUT.
    @param label_prefix: prefix of label to be matched, e.g., |board:|
    @param afe: afe instance.
    @returns the label that matches the prefix or 'None'

    """
    labels = afe.get_labels(name__startswith=label_prefix,
                            host__hostname__in=[hostname])
    if labels and len(labels) == 1:
        return labels[0].name.split(label_prefix, 1)[1]


def get_board_from_afe(hostname, afe):
    """Retrieve given host's board from its labels in the AFE.

    Looks for a host label of the form "board:<board>", and
    returns the "<board>" part of the label.  `None` is returned
    if there is not a single, unique label matching the pattern.

    @param hostname: hostname of given DUT.
    @param afe: afe instance.
    @returns board from label, or `None`.

    """
    return get_label_from_afe(hostname, constants.BOARD_PREFIX, afe)


def get_build_from_afe(hostname, afe):
    """Retrieve the current build for given host from the AFE.

    Looks through the host's labels in the AFE to determine its build.

    @param hostname: hostname of given DUT.
    @param afe: afe instance.
    @returns The current build or None if it could not find it or if there
             were multiple build labels assigned to this host.

    """
    return get_label_from_afe(hostname, constants.VERSION_PREFIX, afe)


def get_sheriffs():
    """
    Polls the javascript file that holds the identity of the sheriff and
    parses it's output to return a list of chromium sheriff email addresses.
    The javascript file can contain the ldap of more than one sheriff, eg:
    document.write('sheriff_one, sheriff_two').

    @return: A list of chroium.org sheriff email addresses to cc on the bug
        if the suite that failed was the bvt suite. An empty list otherwise.
    """
    sheriff_ids = []
    for sheriff_js in _SHERIFF_JS.split(','):
        try:
            url_content = base_utils.urlopen('%s%s'% (
                _CHROMIUM_BUILD_URL, sheriff_js)).read()
        except (ValueError, IOError) as e:
            logging.error('could not parse sheriff from url %s%s: %s',
                           _CHROMIUM_BUILD_URL, sheriff_js, str(e))
        else:
            ldaps = re.search(r"document.write\('(.*)'\)", url_content)
            if not ldaps:
                logging.error('Could not retrieve sheriff ldaps for: %s',
                               url_content)
                continue
            sheriff_ids += ['%s@chromium.org' % alias.replace(' ', '')
                            for alias in ldaps.group(1).split(',')]
    return sheriff_ids
