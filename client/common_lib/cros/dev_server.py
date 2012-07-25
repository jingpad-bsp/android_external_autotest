# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from distutils import version
import logging
import urllib2
import HTMLParser
import cStringIO

from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib.cros import retry
# TODO(cmasone): redo this class using requests module; http://crosbug.com/30107


CONFIG = global_config.global_config


class MarkupStripper(HTMLParser.HTMLParser):
    """HTML parser that strips HTML tags, coded characters like &amp;

    Works by, basically, not doing anything for any tags, and only recording
    the content of text nodes in an internal data structure.
    """
    def __init__(self):
        self.reset()
        self.fed = []


    def handle_data(self, d):
        """Consume content of text nodes, store it away."""
        self.fed.append(d)


    def get_data(self):
        """Concatenate and return all stored data."""
        return ''.join(self.fed)


def _get_image_storage_server():
    return CONFIG.get_config_value('CROS', 'image_storage_server', type=str)


def _get_dev_server_list():
    return CONFIG.get_config_value('CROS', 'dev_server', type=list, default=[])


def _get_crash_server_list():
    return CONFIG.get_config_value('CROS', 'crash_server', type=list,
        default=[])


def remote_devserver_call(method):
    """A decorator to use with remote devserver calls.

    This decorator converts urllib2.HTTPErrors into DevServerExceptions with
    any embedded error info converted into plain text.
    """
    @retry.retry(urllib2.URLError)
    def wrapper(*args, **kwargs):
        """This wrapper actually catches the HTTPError."""
        try:
            return method(*args, **kwargs)
        except urllib2.HTTPError as e:
            error_markup = e.read()
            strip = MarkupStripper()
            try:
                strip.feed(error_markup.decode('utf_32'))
            except UnicodeDecodeError:
                strip.feed(error_markup)
            raise DevServerException(strip.get_data())

    return wrapper


class DevServerException(Exception):
    """Raised when the dev server returns a non-200 HTTP response."""
    pass



# TODO(sosa): Make this class use sub-classes of a common Server class rather
# than if/else cases with crash server/devserver.
class DevServer(object):
    """Helper class for interacting with the Dev Server via http."""


    _CRASH_SERVER_RPC_CALLS = set(['stage_debug', 'symbolicate_dump'])


    def __init__(self, dev_host=None, crash_host=None):
        """Constructor.

        Args:
        @param dev_host: Address of the Dev Server.
                         Defaults to None.  If not set, CROS.dev_server is used.
        """
        if dev_host:
            self._dev_servers = [dev_host]
        else:
            self._dev_servers = _get_dev_server_list()

        if crash_host:
            self._crash_servers = [crash_host]
        else:
            self._crash_servers = _get_crash_server_list()


    @staticmethod
    def create(dev_host=None, crash_host=None):
        """Wraps the constructor.  Purely for mocking purposes."""
        return DevServer(dev_host, crash_host)


    @staticmethod
    def _server_for_hashing_value(servers, hashing_value):
        """Returns the server in servers to use for the given hashing_value.
        Args:
        @param servers: List of servers
        @param hashing_value: The value that determines which server to use.
        """
        return servers[hash(hashing_value) % len(servers)]


    @classmethod
    def devserver_url_for_build(cls, build):
        """Returns the devserver url which contains the build.

        Args:
        @param build:  The build name i.e. builder/version that is being tested.
        """
        return cls._server_for_hashing_value(_get_dev_server_list(), build)


    def _servers_for(self, method):
        """Return the list of servers to use for the given method."""
        if method in DevServer._CRASH_SERVER_RPC_CALLS:
            return self._crash_servers
        else:
            return self._dev_servers


    def _build_call(self, method, hashing_value, **kwargs):
        """Build a URL that calls |method|, passing |kwargs|.

        Build a URL that calls |method| on the dev server, passing a set
        of key/value pairs built from the dict |kwargs|.

        @param method: the dev server method to call.
        @param hashing_value: a value to hash against when determining which
          devserver to use.
        @param kwargs: a dict mapping arg names to arg values
        @return the URL string
        """
        # If we have multiple devservers set up, we hash against the hashing
        # value to give us an index of the devserver to use.  The hashing value
        # must be the same for RPC's that should go to the same devserver.
        server_pool = self._servers_for(method)
        server = self._server_for_hashing_value(server_pool, hashing_value)
        argstr = '&'.join(map(lambda x: "%s=%s" % x, kwargs.iteritems()))
        return "%(host)s/%(method)s?%(args)s" % {'host': server,
                                                 'method': method,
                                                 'args': argstr}


    def _build_all_calls(self, method, **kwargs):
        """Builds a list of URLs that makes RPC calls on all devservers.

        Build a URL that calls |method| on the dev server, passing a set
        of key/value pairs built from the dict |kwargs|.

        @param method: the dev server method to call.
        @param kwargs: a dict mapping arg names to arg values
        @return the URL string
        """
        calls = []
        for hashing_index in range(len(self._servers_for(method))):
            calls.append(self._build_call(method, hashing_value=hashing_index,
                                          **kwargs))

        return calls


    @remote_devserver_call
    def trigger_download(self, image, synchronous=True):
        """Tell the dev server to download and stage |image|.

        Tells the corresponding dev server to fetch |image|
        from the image storage server named by _get_image_storage_server().

        If |synchronous| is True, waits for the entire download to finish
        staging before returning. Otherwise only the artifacts necessary
        to start installing images onto DUT's will be staged before returning.
        A caller can then call finish_download to guarantee the rest of the
        artifacts have finished staging.

        @param image: the image to fetch and stage.
        @param synchronous: if True, waits until all components of the image are
                staged before returning.
        @raise DevServerException upon any return code that's not HTTP OK.
        """
        call = self._build_call(
            'download', hashing_value=image,
            archive_url=_get_image_storage_server() + image)
        response = urllib2.urlopen(call)
        was_successful = response.read() == 'Success'
        if was_successful and synchronous:
            self.finish_download(image)
        elif not was_successful:
            raise DevServerException("trigger_download for %s failed;"
                                     "HTTP OK not accompanied by 'Success'." %
                                     image)


    @remote_devserver_call
    def finish_download(self, image):
        """Tell the dev server to finish staging |image|.

        If trigger_download is called with synchronous=False, it will return
        before all artifacts have been staged. This method contacts the
        devserver and blocks until all staging is completed and should be
        called after a call to trigger_download.

        @param image: the image to fetch and stage.
        @raise DevServerException upon any return code that's not HTTP OK.
        """
        call = self._build_call(
            'wait_for_status',
            hashing_value=image,
            archive_url=_get_image_storage_server() + image)
        if urllib2.urlopen(call).read() != 'Success':
            raise DevServerException("finish_download for %s failed;"
                                     "HTTP OK not accompanied by 'Success'." %
                                     image)


    @remote_devserver_call
    def list_control_files(self, build):
        """Ask the dev server to list all control files for |build|.

        Ask the corresponding dev server to list all control files
        for |build|.

        @param build: The build (e.g. x86-mario-release/R18-1586.0.0-a1-b1514)
                      whose control files the caller wants listed.
        @return None on failure, or a list of control file paths
                (e.g. server/site_tests/autoupdate/control)
        @raise DevServerException upon any return code that's not HTTP OK.
        """
        call = self._build_call('controlfiles', hashing_value=build,
                                build=build)
        response = urllib2.urlopen(call)
        return [line.rstrip() for line in response]


    @remote_devserver_call
    def get_control_file(self, build, control_path):
        """Ask the dev server for the contents of a control file.

        Ask the corresponding dev server for the contents of the
        control file at |control_path| for |build|.

        @param build: The build (e.g. x86-mario-release/R18-1586.0.0-a1-b1514)
                      whose control files the caller wants listed.
        @param control_path: The file to list
                             (e.g. server/site_tests/autoupdate/control)
        @return The contents of the desired file.
        @raise DevServerException upon any return code that's not HTTP OK.
        """
        call = self._build_call('controlfiles',
                                hashing_value=build,
                                build=build, control_path=control_path)
        return urllib2.urlopen(call).read()


    @remote_devserver_call
    def symbolicate_dump(self, minidump_path, build):
        """Ask the dev server to symbolicate the dump at minidump_path.

        Stage the debug symbols for |build| and, if that works, ask the
        corresponding dev server to symbolicate the dump at
        minidump_path.

        @param minidump_path: the on-disk path of the minidump.
        @param build: The build (e.g. x86-mario-release/R18-1586.0.0-a1-b1514)
                      whose debug symbols are needed for symbolication.
        @return The contents of the stack trace
        @raise DevServerException upon any return code that's not HTTP OK.
        """
        try:
            import requests
        except ImportError:
            logging.warning("Can't 'import requests' to connect to dev server.")
            return ''
        # Stage debug symbols.
        call = self._build_call(
            'stage_debug',
            hashing_value=build,
            archive_url=_get_image_storage_server() + build)
        request = requests.get(call)
        if (request.status_code != requests.codes.ok or
            request.text != 'Success'):
            error_fd = cStringIO.StringIO(request.text)
            raise urllib2.HTTPError(call,
                                    request.status_code,
                                    request.text,
                                    request.headers,
                                    error_fd)
        # Symbolicate minidump.
        call = self._build_call('symbolicate_dump', hashing_value=build)
        request = requests.post(call,
                                files={'minidump': open(minidump_path, 'rb')})
        if request.status_code == requests.codes.OK:
            return request.text
        error_fd = cStringIO.StringIO(request.text)
        raise urllib2.HTTPError(call,
                                request.status_code,
                                request.text,
                                request.headers,
                                error_fd)


    @remote_devserver_call
    def get_latest_build(self, target, milestone=''):
        """Ask the dev server for the latest build for a given target.

        Ask the corresponding dev server for the latest build for
        |target|.

        @param target: The build target, typically a combination of the board
                       and the type of build e.g. x86-mario-release.
        @param milestone:  For latest build set to '', for builds only in a
                           specific milestone set to a str of format Rxx
                           (e.g. R16). Default: ''. Since we are dealing with a
                           webserver sending an empty string, '', ensures that
                           the variable in the URL is ignored as if it was set
                           to None.
        @return A string of the returned build e.g. R20-2226.0.0.
        @raise DevServerException upon any return code that's not HTTP OK.
        """
        calls = self._build_all_calls('latestbuild', target=target,
                                      milestone=milestone)
        latest_builds = []
        for call in calls:
            latest_builds.append(urllib2.urlopen(call).read())

        return max(latest_builds, key=version.LooseVersion)
