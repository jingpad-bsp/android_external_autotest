# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import httplib
import logging
import urllib2

from autotest_lib.client.common_lib import global_config


CONFIG = global_config.global_config


def _get_image_storage_server():
    return CONFIG.get_config_value('CROS', 'image_storage_server', type=str)


def _get_dev_server():
    return CONFIG.get_config_value('CROS', 'dev_server', type=str)


class DevServer(object):
    """Helper class for interacting with the Dev Server via http."""
    def __init__(self, dev_host):
        """Constructor.

        Args:
        @param host: Address of the Dev Server.
        """
        self._dev_server = dev_host if dev_host else _get_dev_server()


    def trigger_download(self, image):
        """Tell the dev server to download and stage |image|.

        Tells the dev server at |self._dev_server| to fetch |image|
        from the image storage server named by _get_image_storage_server().

        @param image: the image to fetch and stage.
        @return True if the remote call returns HTTP OK, False if it returns
                an internal server error.
        @throws urllib2.HTTPError upon any return code that's not 200 or 500
        """
        try:
            call = self._build_call(
                method='download',
                named_args={'archive_url': _get_image_storage_server() + image})
            response = urllib2.urlopen(call)
            return response.read() == 'Success'
        except urllib2.HTTPError as e:
            if e.code == httplib.INTERNAL_SERVER_ERROR:
                return False
            else:
                logging.debug(e)
                raise


    def _build_call(self, method, named_args):
        """Build a URL that calls |method|, passing |named_args|.

        Build a URL that calls |method| on the dev server, passing a set
        of key/value pairs built from the dict |named_args|.

        @param method: the dev server method to call.
        @param named_args: a dict mapping arg names to arg values
        @return the URL string
        """
        argstr = '&'.join(map(lambda x: "%s=%s" % x, named_args.iteritems()))
        return "%(host)s/%(method)s?%(args)s" % { 'host': self._dev_server,
                                                  'method': method,
                                                  'args': argstr }
