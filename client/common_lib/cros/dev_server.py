# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import httplib
import logging
import urllib2

from autotest_lib.client.common_lib import global_config
# TODO(cmasone): redo this class using requests module; http://crosbug.com/30107

CONFIG = global_config.global_config


def _get_image_storage_server():
    return CONFIG.get_config_value('CROS', 'image_storage_server', type=str)


def _get_dev_server():
    return CONFIG.get_config_value('CROS', 'dev_server', type=str)


def remote_devserver_call(internal_error_return_val):
    """A decorator to use with remote devserver calls.

    This decorater handles httplib.INTERNAL_SERVER_ERROR's cleanly while
    raising all other exceptions. It requires that you pass in the value you
    want the method to return when it receives a httplib.INTERNAL_SERVER_ERROR.
    """
    def wrapper(method):
      """Wrapper just wraps the method."""
      def inner_wrapper(*args, **kwargs):
        """This wrapper actually catches the httplib.INTERNAL_SERVER_ERROR."""
        try:
            return method(*args, **kwargs)
        except urllib2.HTTPError as e:
            if e.code == httplib.INTERNAL_SERVER_ERROR:
                return internal_error_return_val
            else:
                raise

      return inner_wrapper

    return wrapper


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


    @remote_devserver_call(False)
    def trigger_download(self, image, synchronous=True):
        """Tell the dev server to download and stage |image|.

        Tells the dev server at |self._dev_server| to fetch |image|
        from the image storage server named by _get_image_storage_server().

        If |synchronous| is True, waits for the entire download to finish
        staging before returning. Otherwise only the artifacts necessary
        to start installing images onto DUT's will be staged before returning.
        A caller can then call finish_download to guarantee the rest of the
        artifacts have finished staging.

        @param image: the image to fetch and stage.
        @param synchronous: if True, waits until all components of the image are
                staged before returning.
        @return True if the remote call returns HTTP OK, False if it returns
                an internal server error.
        @raise urllib2.HTTPError upon any return code that's not 200 or 500.
        """
        call = self._build_call(
            'download',
            archive_url=_get_image_storage_server() + image)
        response = urllib2.urlopen(call)
        was_successful = response.read() == 'Success'
        if was_successful and synchronous:
            return self.finish_download(image)
        else:
            return was_successful


    @remote_devserver_call(False)
    def finish_download(self, image):
        """Tell the dev server to finish staging |image|.

        If trigger_download is called with synchronous=False, it will return
        before all artifacts have been staged. This method contacts the
        devserver and blocks until all staging is completed and should be
        called after a call to trigger_download.

        @param image: the image to fetch and stage.
        @return True if the remote call returns HTTP OK, False if it returns
                an internal server error.
        @raise urllib2.HTTPError upon any return code that's not 200 or 500.
        """
        call = self._build_call(
            'wait_for_status',
            archive_url=_get_image_storage_server() + image)
        response = urllib2.urlopen(call)
        return response.read() == 'Success'


    @remote_devserver_call(None)
    def list_control_files(self, build):
        """Ask the dev server to list all control files for |build|.

        Ask the dev server at |self._dev_server| to list all control files
        for |build|.

        @param build: The build (e.g. x86-mario-release/R18-1586.0.0-a1-b1514)
                      whose control files the caller wants listed.
        @return None on failure, or a list of control file paths
                (e.g. server/site_tests/autoupdate/control)
        @raise urllib2.HTTPError upon any return code that's not 200 or 500.
        """
        call = self._build_call('controlfiles', build=build)
        response = urllib2.urlopen(call)
        return [line.rstrip() for line in response]


    @remote_devserver_call(None)
    def get_control_file(self, build, control_path):
        """Ask the dev server for the contents of a control file.

        Ask the dev server at |self._dev_server| for the contents of the
        control file at |control_path| for |build|.

        @param build: The build (e.g. x86-mario-release/R18-1586.0.0-a1-b1514)
                      whose control files the caller wants listed.
        @param control_path: The file to list
                             (e.g. server/site_tests/autoupdate/control)
        @return The contents of the desired file, or None
        @raise urllib2.HTTPError upon any return code that's not 200 or 500.
        """
        call = self._build_call('controlfiles',
                                build=build, control_path=control_path)
        return urllib2.urlopen(call).read()


    def symbolicate_dump(self, minidump_path, build):
        """Ask the dev server to symbolicate the dump at minidump_path.

        Stage the debug symbols for |build| and, if that works, ask the
        dev server at |self._dev_server| to symbolicate the dump at
        minidump_path.

        @param minidump_path: the on-disk path of the minidump.
        @param build: The build (e.g. x86-mario-release/R18-1586.0.0-a1-b1514)
                      whose debug symbols are needed for symbolication.
        @return The contents of the stack trace
        @raise urllib2.HTTPError upon any return code that's not 200.
        """
        try:
            import requests
        except ImportError:
            logging.warning("Can't 'import requests' to connect to dev server.")
            return ''
        # Stage debug symbols.
        call = self._build_call(
            'stage_debug',
            archive_url=_get_image_storage_server() + build)
        request = requests.get(call)
        if (request.status_code != requests.codes.ok or
            request.text != 'Success'):
            raise urllib2.HTTPError(call,
                                    request.status_code,
                                    request.text,
                                    request.headers,
                                    None)
        # Symbolicate minidump.
        call = self._build_call('symbolicate_dump')
        request = requests.post(call,
                                files={'minidump': open(minidump_path, 'rb')})
        if request.status_code == requests.codes.OK:
            return request.text
        raise urllib2.HTTPError(call,
                                request.status_code,
                                '%d' % request.status_code,
                                request.headers,
                                None)


    @remote_devserver_call(None)
    def get_latest_build(self, target, milestone=''):
        """Ask the dev server for the latest build for a given target.

        Ask the dev server at |self._dev_server|for the latest build for
        |target|.

        @param target: The build target, typically a combination of the board
                       and the type of build e.g. x86-mario-release.
        @param milestone:  For latest build set to '', for builds only in a
                           specific milestone set to a str of format Rxx
                           (e.g. R16). Default: ''. Since we are dealing with a
                           webserver sending an empty string, '', ensures that
                           the variable in the URL is ignored as if it was set
                           to None.
        @return A string of the returned build e.g. R18-1586.0.0-a1-b1514
                or None.
        @raise urllib2.HTTPError upon any return code that's not 200 or 500.
        """
        call = self._build_call('latestbuild', target=target,
                                milestone=milestone)
        return urllib2.urlopen(call).read()
