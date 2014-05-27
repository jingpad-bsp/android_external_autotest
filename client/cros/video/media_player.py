# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.video import method_logger


class VideoPlayer(object):
    """
    Provides interface to interact with and control video playback via js.

    """


    @method_logger.log
    def __init__(self, tab, full_url, video_src_path, video_id,
                 time_out_for_events_s, time_btwn_polling_s):
        """
        @param tab: object, tab to interact with the tab in the browser.
        @param full_url: string, full url pointing to html file to load.
        @param video_src_path: path, complete path to video used for test.
        @param video_id: string, name of the video_id element in the html file.
        @param time_out_for_events_s: integer, how long to wait for an event
                                      before timing out
        @param time_btwn_polling_s: integer, how long to wait between one call
                                    to check a condition and the next.

        """
        self.tab = tab
        self.full_url = full_url
        self.video_source_path = video_src_path
        self.video_id = video_id
        self.time_out_for_events_s = time_out_for_events_s
        self.time_btwn_polling_s = time_btwn_polling_s


    @method_logger.log
    def load_video(self):
        """
         Loads video and waits for video to be ready to play.

        """
        self.tab.Navigate(self.full_url)
        self._wait_for_page_to_load()

        # Set video source to desired path in the html file.
        self.tab.ExecuteJavaScript(
            'loadVideoSource("%s")' % self.video_source_path)

        self._wait_for_canplay_event()


    @method_logger.log
    def seek_video_to_timestamp(self, timestamp):
        """
        Uses javascript to set currentTime property of video to desired time.

        @param timestamp: timedelta, instance of time to navigate video to.

        """

        cmd = "%s.currentTime=%.3f" % (
            self.video_id, timestamp.total_seconds())
        self.tab.ExecuteJavaScript(cmd)



    @method_logger.log
    def wait_for_video_to_seek(self):
        """
         Waits for the javascript 'seeked' event.

        """
        def has_video_finished_seeking():
            """
            Helper function to get video seeking status via javascript.

            """
            return self.tab.EvaluateJavaScript('finishedSeeking()')

        exception_msg = 'Video did not complete seeking in time.'

        self._wait_for_event(has_video_finished_seeking, exception_msg)

        # TODO: Fix this.
        # There is a lag between assigning a value to the currentTimeElement
        # and the new assigned value being displayed.
        time.sleep(0.1)


    @method_logger.log
    def _wait_for_page_to_load(self):
        """
         Waits for javascript objects to be defined.

         When we a valid video object we say the page is ready to accept more
         commands.

        """
        def has_page_loaded():
            """
            Uses javascript to check if page objects have been defined.

            If objects are defined then we know we are able to execute further
            commands in the page.

            """
            result = self.tab.EvaluateJavaScript('(typeof %s)' % self.video_id)
            return result != 'undefined'

        exception_msg = 'HTML page did not load at url : %s' % self.full_url

        self._wait_for_event(has_page_loaded, exception_msg)


    @method_logger.log
    def _wait_for_canplay_event(self):
        """
         Waits for the javascript 'canplay' event.

        """
        def can_play_video():
            """
            Uses javascript to check if the 'canplay' event was raised.

            Executing the javascript 'canplay()' function we return the value of
            a bool variable set to true when the canplay event is raised.

            """
            return self.tab.EvaluateJavaScript('canplay()')

        exception_msg = 'canplay event was not received in time'

        self._wait_for_event(can_play_video, exception_msg)


    @method_logger.log
    def _wait_for_event(self, predicate_function, exception_msg):
        """
         Helper method to wait for a desired condition.

         @param predicate_function: object, function which returns true when
                                    desired condition is achieved.
         @param exception_msg: string, an exception message to show when desired
                               condition is not achieved in allowed time.

        """
        fullmsg = exception_msg + ' Waited for %ss' % self.time_out_for_events_s

        utils.poll_for_condition(predicate_function,
                                 error.TestError(fullmsg),
                                 self.time_out_for_events_s,
                                 self.time_btwn_polling_s)