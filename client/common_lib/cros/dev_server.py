# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import httplib
import urllib2

from autotest_lib.client.common_lib import global_config


CONFIG = global_config.global_config


def _get_image_storage_server():
    return CONFIG.get_config_value('CROS', 'image_storage_server', type=str)


def _get_dev_server():
    return CONFIG.get_config_value('CROS', 'dev_server', type=str)


class DevServer(object):
    """Helper class for interacting with the Dev Server via http."""
    def __init__(self, dev_host=None):
        """Constructor.

        Args:
        @param dev_host: Address of the Dev Server.
                         Defaults to None.  If not set, CROS.dev_server is used.
        """
        self._dev_server = dev_host if dev_host else _get_dev_server()


    @staticmethod
    def create(dev_host=None):
        """Wraps the constructor.  Purely for mocking purposes."""
        return DevServer(dev_host)


    def _build_call(self, method, **kwargs):
        """Build a URL that calls |method|, passing |kwargs|.

        Build a URL that calls |method| on the dev server, passing a set
        of key/value pairs built from the dict |kwargs|.

        @param method: the dev server method to call.
        @param kwargs: a dict mapping arg names to arg values
        @return the URL string
        """
        argstr = '&'.join(map(lambda x: "%s=%s" % x, kwargs.iteritems()))
        return "%(host)s/%(method)s?%(args)s" % {'host': self._dev_server,
                                                 'method': method,
                                                 'args': argstr}


    def trigger_download(self, image):
        """Tell the dev server to download and stage |image|.

        Tells the dev server at |self._dev_server| to fetch |image|
        from the image storage server named by _get_image_storage_server().

        @param image: the image to fetch and stage.
        @return True if the remote call returns HTTP OK, False if it returns
                an internal server error.
        @throws urllib2.HTTPError upon any return code that's not 200 or 500.
        """
        try:
            call = self._build_call(
                'download',
                archive_url=_get_image_storage_server() + image)
            response = urllib2.urlopen(call)
            return response.read() == 'Success'
        except urllib2.HTTPError as e:
            if e.code == httplib.INTERNAL_SERVER_ERROR:
                return False
            else:
                raise


    def list_control_files(self, build):
        """Ask the dev server to list all control files for |build|.

        Ask the dev server at |self._dev_server| to list all control files
        for |build|.

        @param build: The build (e.g. x86-mario-release/R18-1586.0.0-a1-b1514)
                      whose control files the caller wants listed.
        @return None on failure, or a list of control file paths
                (e.g. server/site_tests/autoupdate/control)
        @throws urllib2.HTTPError upon any return code that's not 200 or 500.
        """
        try:
            call = self._build_call('controlfiles', build=build)
            response = urllib2.urlopen(call)
            return [line.rstrip() for line in response]
        except urllib2.HTTPError as e:
            if e.code == httplib.INTERNAL_SERVER_ERROR:
                return None
            else:
                raise


    def get_control_file(self, build, control_path):
        """Ask the dev server for the contents of a control file.

        Ask the dev server at |self._dev_server|for the contents of the
        control file at |control_path| for |build|.

        @param build: The build (e.g. x86-mario-release/R18-1586.0.0-a1-b1514)
                      whose control files the caller wants listed.
        @param control_path: The file to list
                             (e.g. server/site_tests/autoupdate/control)
        @return The contents of the desired file, or None
        @throws urllib2.HTTPError upon any return code that's not 200 or 500.
        """
        try:
            call = self._build_call('controlfiles',
                                    build=build, control_path=control_path)
            return urllib2.urlopen(call).read()
        except urllib2.HTTPError as e:
            if e.code == httplib.INTERNAL_SERVER_ERROR:
                return None
            else:
                raise
