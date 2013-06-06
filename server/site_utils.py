# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.server.cros.dynamic_suite import constants


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


