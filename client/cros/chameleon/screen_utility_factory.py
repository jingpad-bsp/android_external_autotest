# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.cros.chameleon import resolution_comparison


class ScreenUtilityFactory(object):
    """A factory to generate utilities for screen comparison test.

    This factory creates the utilities, according to the properties of
    the CrOS. For example, a CrOS connected to VGA can use a VGA specific
    algorithm for screen comparison.

    """

    def __init__(self, chameleon_port, display_facade):
        """Initializes the ScreenUtilityFactory objects."""
        self._chameleon_port = chameleon_port
        self._display_facade = display_facade


    def create_resolution_comparer(self):
        """Creates a resolution comparer object."""
        if self._display_facade.get_external_connector_name().startswith('VGA'):
            return resolution_comparison.VgaResolutionComparer(
                    self._chameleon_port, self._display_facade)
        else:
            return resolution_comparison.ExactMatchResolutionComparer(
                    self._chameleon_port, self._display_facade)
