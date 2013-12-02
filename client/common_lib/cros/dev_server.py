# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from distutils import version
import httplib
import json
import logging
import urllib2
import HTMLParser
import cStringIO
import re
import sys

from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib import utils
from autotest_lib.client.common_lib.cros import retry
from autotest_lib.client.bin import utils as site_utils
from autotest_lib.site_utils.graphite import stats
# TODO(cmasone): redo this class using requests module; http://crosbug.com/30107


CONFIG = global_config.global_config
# This file is generated at build time and specifies, per suite and per test,
# the DEPENDENCIES list specified in each control file.  It's a dict of dicts:
# {'bvt':   {'/path/to/autotest/control/site_tests/test1/control': ['dep1']}
#  'suite': {'/path/to/autotest/control/site_tests/test2/control': ['dep2']}
#  'power': {'/path/to/autotest/control/site_tests/test1/control': ['dep1'],
#            '/path/to/autotest/control/site_tests/test3/control': ['dep3']}
# }
DEPENDENCIES_FILE = 'test_suites/dependency_info'
# Number of seconds for caller to poll devserver's is_staged call to check if
# artifacts are staged.
_ARTIFACT_STAGE_POLLING_INTERVAL = 5
# Artifacts that should be staged when client calls devserver RPC to stage an
# image.
_ARTIFACTS_TO_BE_STAGED_FOR_IMAGE = 'full_payload,test_suites,stateful'
# Artifacts that should be staged when client calls devserver RPC to stage an
# image with autotest artifact.
_ARTIFACTS_TO_BE_STAGED_FOR_IMAGE_WITH_AUTOTEST = ('full_payload,test_suites,'
                                                   'autotest,stateful')


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


def _get_canary_channel_server():
    """
    Get the url of the canary-channel server,
    eg: gsutil://chromeos-releases/canary-channel/<board>/<release>

    @return: The url to the canary channel server.
    """
    return CONFIG.get_config_value('CROS', 'canary_channel_server', type=str)


def _get_storage_server_for_artifacts(artifacts=None):
    """Gets the appropriate storage server for the given artifacts.

    @param artifacts: A list of artifacts we need to stage.
    @return: The address of the storage server that has these artifacts.
             The default image storage server if no artifacts are specified.
    """
    factory_artifact = global_config.global_config.get_config_value(
            'CROS', 'factory_artifact', type=str, default='')
    if artifacts and factory_artifact and factory_artifact in artifacts:
        return _get_canary_channel_server()
    return _get_image_storage_server()


def _get_dev_server_list():
    return CONFIG.get_config_value('CROS', 'dev_server', type=list, default=[])


def _get_crash_server_list():
    return CONFIG.get_config_value('CROS', 'crash_server', type=list,
        default=[])


def remote_devserver_call(timeout_min=30):
    """A decorator to use with remote devserver calls.

    This decorator converts urllib2.HTTPErrors into DevServerExceptions with
    any embedded error info converted into plain text.
    The method retries on urllib2.URLError to avoid devserver flakiness.
    """
    #pylint: disable=C0111
    def inner_decorator(method):

        @retry.retry(urllib2.URLError, timeout_min=timeout_min)
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

    return inner_decorator


class DevServerException(Exception):
    """Raised when the dev server returns a non-200 HTTP response."""
    pass


class DevServer(object):
    """Base class for all DevServer-like server stubs.

    This is the base class for interacting with all Dev Server-like servers.
    A caller should instantiate a sub-class of DevServer with:

    host = SubClassServer.resolve(build)
    server = SubClassServer(host)
    """
    _MIN_FREE_DISK_SPACE_GB = 20

    def __init__(self, devserver):
        self._devserver = devserver


    def url(self):
        """Returns the url for this devserver."""
        return self._devserver


    @staticmethod
    def devserver_healthy(devserver, timeout_min=0.1):
        """Returns True if the |devserver| is healthy to stage build.

        @param devserver: url of the devserver.
        @param timeout_min: How long to wait in minutes before deciding the
                            the devserver is not up (float).
        """
        server_name = re.sub(r':\d+$', '', devserver.lstrip('http://'))
        # statsd treats |.| as path separator.
        server_name = server_name.replace('.', '_')
        call = DevServer._build_call(devserver, 'check_health')

        @remote_devserver_call(timeout_min=timeout_min)
        def make_call():
            """Inner method that makes the call."""
            return utils.urlopen_socket_timeout(call,
                timeout=timeout_min * 60).read()

        try:
            result_dict = json.load(cStringIO.StringIO(make_call()))
            free_disk = result_dict['free_disk']
            stats.Gauge(server_name).send('free_disk', free_disk)

            skip_devserver_health_check = CONFIG.get_config_value('CROS',
                                              'skip_devserver_health_check',
                                              type=bool)
            if skip_devserver_health_check:
                logging.debug('devserver health check is skipped.')
            elif (free_disk < DevServer._MIN_FREE_DISK_SPACE_GB):
                logging.error('Devserver check_health failed. Free disk space '
                              'is low. Only %dGB is available.', free_disk)
                stats.Counter(server_name +
                              '.devserver_not_healthy').increment()
                return False

            # This counter indicates the load of a devserver. By comparing the
            # value of this counter for all devservers, we can evaluate the
            # load balancing across all devservers.
            stats.Counter(server_name + '.devserver_healthy').increment()
            return True
        except Exception as e:
            logging.error('Devserver call failed: "%s", timeout: %s seconds,'
                          ' Error: %s', call, timeout_min * 60, e)
            stats.Counter(server_name + '.devserver_not_healthy').increment()
            return False


    @staticmethod
    def _build_call(host, method, **kwargs):
        """Build a URL to |host| that calls |method|, passing |kwargs|.

        Builds a URL that calls |method| on the dev server defined by |host|,
        passing a set of key/value pairs built from the dict |kwargs|.

        @param host: a string that is the host basename e.g. http://server:90.
        @param method: the dev server method to call.
        @param kwargs: a dict mapping arg names to arg values.
        @return the URL string.
        """
        argstr = '&'.join(map(lambda x: "%s=%s" % x, kwargs.iteritems()))
        return "%(host)s/%(method)s?%(argstr)s" % dict(
                host=host, method=method, argstr=argstr)


    def build_call(self, method, **kwargs):
        """Builds a devserver RPC string that can be invoked using urllib.open.

        @param method: remote devserver method to call.
        """
        return self._build_call(self._devserver, method, **kwargs)


    @classmethod
    def build_all_calls(cls, method, **kwargs):
        """Builds a list of URLs that makes RPC calls on all devservers.

        Build a URL that calls |method| on the dev server, passing a set
        of key/value pairs built from the dict |kwargs|.

        @param method: the dev server method to call.
        @param kwargs: a dict mapping arg names to arg values
        @return the URL string
        """
        calls = []
        # Note we use cls.servers as servers is class specific.
        for server in cls.servers():
            if cls.devserver_healthy(server):
                calls.append(cls._build_call(server, method, **kwargs))

        return calls


    @staticmethod
    def servers():
        """Returns a list of servers that can serve as this type of server."""
        raise NotImplementedError()


    @classmethod
    def resolve(cls, build):
        """"Resolves a build to a devserver instance.

        @param build: The build (e.g. x86-mario-release/R18-1586.0.0-a1-b1514).
        """
        devservers = cls.servers()
        while devservers:
            hash_index = hash(build) % len(devservers)
            devserver = devservers.pop(hash_index)
            if cls.devserver_healthy(devserver):
                return cls(devserver)
        else:
            logging.error('All devservers are currently down!!!')
            raise DevServerException('All devservers are currently down!!!')


class CrashServer(DevServer):
    """Class of DevServer that symbolicates crash dumps."""
    @staticmethod
    def servers():
        return _get_crash_server_list()


    @remote_devserver_call()
    def symbolicate_dump(self, minidump_path, build):
        """Ask the devserver to symbolicate the dump at minidump_path.

        Stage the debug symbols for |build| and, if that works, ask the
        devserver to symbolicate the dump at |minidump_path|.

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

        stats.Counter('CrashServer.symbolicate_dump').increment()
        timer = stats.Timer('CrashServer.symbolicate_dump')
        timer.start()
        # Symbolicate minidump.
        call = self.build_call('symbolicate_dump',
                               archive_url=_get_image_storage_server() + build)
        request = requests.post(
                call, files={'minidump': open(minidump_path, 'rb')})
        if request.status_code == requests.codes.OK:
            timer.stop()
            return request.text

        error_fd = cStringIO.StringIO(request.text)
        raise urllib2.HTTPError(
                call, request.status_code, request.text, request.headers,
                error_fd)


class ImageServer(DevServer):
    """Class for DevServer that handles image-related RPCs.

    The calls to devserver to stage artifacts, including stage and download, are
    made in async mode. That is, when caller makes an RPC |stage| to request
    devserver to stage certain artifacts, devserver handles the call and starts
    staging artifacts in a new thread, and return |Success| without waiting for
    staging being completed. When caller receives message |Success|, it polls
    devserver's is_staged call until all artifacts are staged.
    Such mechanism is designed to prevent cherrypy threads in devserver being
    running out, as staging artifacts might take long time, and cherrypy starts
    with a fixed number of threads that handle devserver rpc.
    """
    @staticmethod
    def servers():
        return _get_dev_server_list()


    @classmethod
    def devserver_url_for_servo(cls, board):
        """Returns the devserver url for use with servo recovery.

        @param board: The board (e.g. 'x86-mario').
        """
        # Ideally, for load balancing we'd select the server based
        # on the board.  For now, to simplify manual steps on the
        # server side, we ignore the board type and hard-code the
        # server as first in the list.
        #
        # TODO(jrbarnette) Once we have automated selection of the
        # build for recovery, we should revisit this.
        url_pattern = CONFIG.get_config_value('CROS',
                                              'servo_url_pattern',
                                              type=str)
        return url_pattern % (cls.servers()[0], board)


    class ArtifactUrls(object):
        """A container for URLs of staged artifacts.

        Attributes:
            full_payload: URL for downloading a staged full release update
            mton_payload: URL for downloading a staged M-to-N release update
            nton_payload: URL for downloading a staged N-to-N release update

        """
        def __init__(self, full_payload=None, mton_payload=None,
                     nton_payload=None):
            self.full_payload = full_payload
            self.mton_payload = mton_payload
            self.nton_payload = nton_payload


    def wait_for_artifacts_staged(self, archive_url, artifacts='', files=''):
        """Polling devserver.is_staged until all artifacts are staged.

        @param archive_url: Google Storage URL for the build.
        @param artifacts: Comma separated list of artifacts to download.
        @param files: Comma separated list of files to download.
        @return: True if all artifacts are staged in devserver.
        """
        call = self.build_call('is_staged',
                               archive_url=archive_url,
                               artifacts=artifacts,
                               files=files)

        def all_staged():
            """Call devserver.is_staged rpc to check if all files are staged.

            @return: True if all artifacts are staged in devserver. False
                     otherwise.
            @rasies DevServerException, the exception is a wrapper of all
                    exceptions that were raised when devserver tried to download
                    the artifacts. devserver raises an HTTPError when an
                    exception was raised in the code. Such exception should be
                    re-raised here to stop the caller from waiting. If the call
                    to devserver failed for connection issue, a URLError
                    exception is raised, and caller should retry the call to
                    avoid such network flakiness.

            """
            try:
                return urllib2.urlopen(call).read() == 'True'
            except urllib2.HTTPError as e:
                error_markup = e.read()
                strip = MarkupStripper()
                try:
                    strip.feed(error_markup.decode('utf_32'))
                except UnicodeDecodeError:
                    strip.feed(error_markup)
                raise DevServerException(strip.get_data())
            except urllib2.URLError as e:
                # Could be connection issue, retry it.
                # For example: <urlopen error [Errno 111] Connection refused>
                return False

        site_utils.poll_for_condition(
                all_staged,
                exception=site_utils.TimeoutError(),
                timeout=sys.maxint,
                sleep_interval=_ARTIFACT_STAGE_POLLING_INTERVAL)
        return True


    def call_and_wait(self, call_name, archive_url, artifacts, files,
                      error_message, expected_response='Success'):
        """Helper method to make a urlopen call, and wait for artifacts staged.

        @param call_name: name of devserver rpc call.
        @param archive_url: Google Storage URL for the build..
        @param artifacts: Comma separated list of artifacts to download.
        @param files: Comma separated list of files to download.
        @param expected_response: Expected response from rpc, default to
                                  |Success|. If it's set to None, do not compare
                                  the actual response. Any response is consider
                                  to be good.
        @param error_message: Error message to be thrown if response does not
                              match expected_response.

        @return: The response from rpc.
        @raise DevServerException upon any return code that's expected_response.

        """
        call = self.build_call(call_name,
                               archive_url=archive_url,
                               artifacts=artifacts,
                               files=files,
                               async=True)
        try:
            response = urllib2.urlopen(call).read()
        except httplib.BadStatusLine as e:
            logging.error(e)
            raise DevServerException('Received Bad Status line, Devserver %s '
                                     'might have gone down while handling '
                                     'the call: %s' % (self.url(), call))

        if expected_response and not response == expected_response:
              raise DevServerException(error_message)

        self.wait_for_artifacts_staged(archive_url, artifacts, files)
        return response


    @remote_devserver_call()
    def stage_artifacts(self, image, artifacts=None, files=None,
                        archive_url=None):
        """Tell the devserver to download and stage |artifacts| from |image|.

        This is the main call point for staging any specific artifacts for a
        given build. To see the list of artifacts one can stage see:

        ~src/platfrom/dev/artifact_info.py.

        This is maintained along with the actual devserver code.

        @param image: the image to fetch and stage.
        @param artifacts: A list of artifacts.
        @param files: A list of files to stage.
        @param archive_url: Optional parameter that has the archive_url to stage
                this artifact from. Default is specified in autotest config +
                image.

        @raise DevServerException upon any return code that's not HTTP OK.
        @raise DevServerException upon any return code that's not HTTP OK.
        """
        assert artifacts or files, 'Must specify something to stage.'
        if not archive_url:
            archive_url = (_get_storage_server_for_artifacts(artifacts) +
                           image)

        artifacts_arg = ','.join(artifacts) if artifacts else ''
        files_arg = ','.join(files) if files else ''
        error_message = ("staging %s for %s failed;"
                         "HTTP OK not accompanied by 'Success'." %
                         ('artifacts=%s files=%s ' % (artifacts_arg, files_arg),
                          image))
        self.call_and_wait(call_name='stage',
                           archive_url=archive_url,
                           artifacts=artifacts_arg,
                           files=files_arg,
                           error_message=error_message)


    @remote_devserver_call()
    def trigger_download(self, image, synchronous=True):
        """Tell the devserver to download and stage |image|.

        Tells the devserver to fetch |image| from the image storage server
        named by _get_image_storage_server().

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
        archive_url = _get_image_storage_server() + image
        artifacts = _ARTIFACTS_TO_BE_STAGED_FOR_IMAGE
        error_message = ("trigger_download for %s failed;"
                         "HTTP OK not accompanied by 'Success'." % image)
        response = self.call_and_wait(call_name='stage',
                                      archive_url=archive_url,
                                      artifacts=artifacts,
                                      files='',
                                      error_message=error_message)
        was_successful = response == 'Success'
        if was_successful and synchronous:
            self.finish_download(image)


    @remote_devserver_call()
    def setup_telemetry(self, build):
        """Tell the devserver to setup telemetry for this build.

        The devserver will stage autotest and then extract the required files
        for telemetry.

        @param build: the build to setup telemetry for.

        @returns path on the devserver that telemetry is installed to.
        """
        archive_url = _get_image_storage_server() + build
        call = self.build_call('setup_telemetry', archive_url=archive_url)
        try:
            response = urllib2.urlopen(call).read()
        except httplib.BadStatusLine as e:
            logging.error(e)
            raise DevServerException('Received Bad Status line, Devserver %s '
                                     'might have gone down while handling '
                                     'the call: %s' % (self.url(), call))
        return response


    @remote_devserver_call()
    def finish_download(self, image):
        """Tell the devserver to finish staging |image|.

        If trigger_download is called with synchronous=False, it will return
        before all artifacts have been staged. This method contacts the
        devserver and blocks until all staging is completed and should be
        called after a call to trigger_download.

        @param image: the image to fetch and stage.
        @raise DevServerException upon any return code that's not HTTP OK.
        """
        archive_url = _get_image_storage_server() + image
        artifacts = _ARTIFACTS_TO_BE_STAGED_FOR_IMAGE_WITH_AUTOTEST
        error_message = ("finish_download for %s failed;"
                         "HTTP OK not accompanied by 'Success'." % image)
        self.call_and_wait(call_name='stage',
                           archive_url=archive_url,
                           artifacts=artifacts,
                           files='',
                           error_message=error_message)


    def get_update_url(self, image):
        """Returns the url that should be passed to the updater.

        @param image: the image that was fetched.
        """
        url_pattern = CONFIG.get_config_value('CROS', 'image_url_pattern',
                                              type=str)
        return (url_pattern % (self.url(), image))


    def _get_image_url(self, image):
        """Returns the url of the directory for this image on the devserver.

        @param image: the image that was fetched.
        """
        url_pattern = CONFIG.get_config_value('CROS', 'image_url_pattern',
                                              type=str)
        return (url_pattern % (self.url(), image)).replace(
                'update', 'static')


    def get_staged_file_url(self, filename, image):
        """Returns the url of a staged file for this image on the devserver."""
        return '/'.join([self._get_image_url(image), filename])


    def get_full_payload_url(self, image):
        """Returns a URL to a staged full payload.

        @param image: the image that was fetched.

        @return A fully qualified URL that can be used for downloading the
                payload.

        """
        return self._get_image_url(image) + '/update.gz'


    def get_test_image_url(self, image):
        """Returns a URL to a staged test image.

        @param image: the image that was fetched.

        @return A fully qualified URL that can be used for downloading the
                image.

        """
        return self._get_image_url(image) + '/chromiumos_test_image.bin'


    @remote_devserver_call()
    def list_control_files(self, build, suite_name=''):
        """Ask the devserver to list all control files for |build|.

        @param build: The build (e.g. x86-mario-release/R18-1586.0.0-a1-b1514)
                      whose control files the caller wants listed.
        @param suite_name: The name of the suite for which we require control
                           files.
        @return None on failure, or a list of control file paths
                (e.g. server/site_tests/autoupdate/control)
        @raise DevServerException upon any return code that's not HTTP OK.
        """
        call = self.build_call('controlfiles', build=build,
                               suite_name=suite_name)
        response = urllib2.urlopen(call)
        return [line.rstrip() for line in response]


    @remote_devserver_call()
    def get_control_file(self, build, control_path):
        """Ask the devserver for the contents of a control file.

        @param build: The build (e.g. x86-mario-release/R18-1586.0.0-a1-b1514)
                      whose control file the caller wants to fetch.
        @param control_path: The file to fetch
                             (e.g. server/site_tests/autoupdate/control)
        @return The contents of the desired file.
        @raise DevServerException upon any return code that's not HTTP OK.
        """
        call = self.build_call('controlfiles', build=build,
                               control_path=control_path)
        return urllib2.urlopen(call).read()


    @remote_devserver_call()
    def get_dependencies_file(self, build):
        """Ask the dev server for the contents of the suite dependencies file.

        Ask the dev server at |self._dev_server| for the contents of the
        pre-processed suite dependencies file (at DEPENDENCIES_FILE)
        for |build|.

        @param build: The build (e.g. x86-mario-release/R21-2333.0.0)
                      whose dependencies the caller is interested in.
        @return The contents of the dependencies file, which should eval to
                a dict of dicts, as per site_utils/suite_preprocessor.py.
        @raise DevServerException upon any return code that's not HTTP OK.
        """
        call = self.build_call('controlfiles',
                               build=build, control_path=DEPENDENCIES_FILE)
        return urllib2.urlopen(call).read()


    @remote_devserver_call()
    def get_latest_build_in_server(self, target, milestone=''):
        """Ask the devserver for the latest build for a given target.

        @param target: The build target, typically a combination of the board
                       and the type of build e.g. x86-mario-release.
        @param milestone:  For latest build set to '', for builds only in a
                           specific milestone set to a str of format Rxx
                           (e.g. R16). Default: ''. Since we are dealing with a
                           webserver sending an empty string, '', ensures that
                           the variable in the URL is ignored as if it was set
                           to None.
        @return A string of the returned build e.g. R20-2226.0.0. Return None
            if no build is found in the devserver for given target and
            milestone.
        """
        call = self.build_call('latestbuild', target=target,
                                milestone=milestone)
        try:
            return urllib2.urlopen(call).read()
        except urllib2.HTTPError:
            return None


    @classmethod
    @remote_devserver_call()
    def get_latest_build(cls, target, milestone=''):
        """Ask all the devservers for the latest build for a given target.

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
        calls = cls.build_all_calls('latestbuild', target=target,
                                    milestone=milestone)
        latest_builds = []
        for call in calls:
            latest_builds.append(urllib2.urlopen(call).read())

        return max(latest_builds, key=version.LooseVersion)
