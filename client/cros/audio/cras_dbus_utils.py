# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module provides cras DBus audio utilities."""

import logging

from autotest_lib.client.cros.audio import cras_utils


def _set_default_main_loop():
    """Sets the gobject main loop to be the event loop for DBus.

    @raises: ImportError if dbus.mainloop.glib can not be imported.

    """
    try:
        import dbus.mainloop.glib
    except ImportError, e:
        logging.exception(
                'Can not import dbus.mainloop.glib: %s. '
                'This method should only be called on Cros device.', e)
        raise
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)


def _get_gobject():
    """Tries to import gobject.

    @returns: The imported gobject module.

    @raises: ImportError if gobject can not be imported.

    """
    try:
        import gobject
    except ImportError, e:
        logging.exception(
                'Can not import gobject: %s. This method should only be '
                'called on Cros device.', e)
        raise
    return gobject


class CrasDBusMonitorError(Exception):
    """Error in CrasDBusMonitor."""
    pass


class CrasDBusMonitor(object):
    """Monitor for DBus signal from Cras."""
    def __init__(self):
        _set_default_main_loop()
        self._iface = cras_utils.get_cras_control_interface()
        self._loop = _get_gobject().MainLoop()
        self._count = 0
        self._target_signal_count = 0


    def wait_for_nodes_changed(self, target_signal_count, timeout_secs):
        """Waits for NodesChanged signal.

        @param target_signal_count: The expected number of signal.
        @param timeout_secs: The timeout in seconds.

        @raises: CrasDBusMonitorError if there is no enough signals before
                 timeout.

        """
        self._target_signal_count = target_signal_count
        signal_match = self._iface.connect_to_signal(
                'NodesChanged', self._nodes_changed_handler)
        _get_gobject().timeout_add(
                timeout_secs * 1000, self._timeout_quit_main_loop)

        # Blocks here until _nodes_changed_handler or _timeout_quit_main_loop
        # quits the loop.
        self._loop.run()

        signal_match.remove()
        if self._count < self._target_signal_count:
            raise CrasDBusMonitorError('Timeout')


    def _nodes_changed_handler(self):
        """Handler for NodesChanged signal."""
        if self._loop.is_running():
            logging.debug('Got NodesChanged signal when loop is running.')
            self._count = self._count + 1
            logging.debug('count = %d', self._count)
            if self._count >= self._target_signal_count:
                logging.debug('Quit main loop')
                self._loop.quit()
        else:
            logging.debug('Got NodesChanged signal when loop is not running.'
                          ' Ignore it')


    def _timeout_quit_main_loop(self):
        """Handler for timeout in main loop.

        @returns: False so this callback will not be called again.

        """
        if self._loop.is_running():
            logging.error('Quit main loop because of timeout')
            self._loop.quit()
        else:
            logging.debug(
                    'Got _quit_main_loop after main loop quits. Ignore it')

        return False
