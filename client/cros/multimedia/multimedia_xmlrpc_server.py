#!/usr/bin/env python
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""XML RPC server for multimedia testing."""

import argparse
import code
import logging
import os
import xmlrpclib

import common   # pylint: disable=W0611
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib.cros import chrome, xmlrpc_server
from autotest_lib.client.cros import constants
from autotest_lib.client.cros.multimedia import audio_utility
from autotest_lib.client.cros.multimedia import display_utility


class MultimediaXmlRpcDelegate(xmlrpc_server.XmlRpcDelegate):
    """XML RPC delegate for multimedia testing."""

    def __init__(self, chrome):
        """Initializes the utility objects."""
        self._utilities = {
                'audio': audio_utility.AudioUtility(chrome),
                'display': display_utility.DisplayUtility(chrome)
        }

    def _dispatch(self, method, params):
        """Dispatches the method to the proper utility.

        We turn off allow_dotted_names option. The method handles the dot
        and dispatches the method to the proper utility, like DisplayUtility.

        """
        try:
            if '.' not in method:
                func = getattr(self, method)
            else:
                util_name, method_name = method.split('.', 1)
                if util_name in self._utilities:
                    func = getattr(self._utilities[util_name], method_name)
                else:
                    raise Exception('unknown utility: %s' % util_name)
        except AttributeError:
            raise Exception('method %s not supported' % method)

        logging.info('Dispatching method %s with args %s',
                     str(func), str(params))
        return func(*params)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--debug', action='store_true', required=False,
                        help=('create a debug console with a ServerProxy "s" '
                              'connecting to the XML RPC sever at localhost'))
    args = parser.parse_args()

    if args.debug:
        s = xmlrpclib.ServerProxy('http://localhost:%d' %
                                  constants.MULTIMEDIA_XMLRPC_SERVER_PORT)
        code.interact(local=locals())
    else:
        logging.basicConfig(level=logging.DEBUG)
        logging.debug('multimedia_xmlrpc_server main...')

        utils.assert_has_X_server()
        os.environ['DISPLAY'] = ':0.0'
        os.environ['XAUTHORITY'] = '/home/chronos/.Xauthority'

        extra_browser_args = ['--enable-gpu-benchmarking']

        with chrome.Chrome(
                extension_paths=[constants.MULTIMEDIA_TEST_EXTENSION],
                extra_browser_args=extra_browser_args) as cr:
            server = xmlrpc_server.XmlRpcServer(
                    'localhost', constants.MULTIMEDIA_XMLRPC_SERVER_PORT)
            server.register_delegate(MultimediaXmlRpcDelegate(cr))
            server.run()
