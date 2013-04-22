# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Touchpad firmware test report in html format."""

import json
import os
import urllib

import common_util
import firmware_log
import test_conf as conf

from firmware_constants import VLOG
from string import Template


class TemplateHtml:
    """An html Template."""

    def __init__(self, image_width, image_height, score_colors):
        self.score_colors = score_colors

        # Define the template of the doc
        self.doc = Template('$head $summary $logs $tail')
        self.table = Template('<table border="3" width="100%"> $gestures '
                              '</table>')
        self.gestures = []

        # Define a template to show a gesture information including
        # the gesture name, variation, prompt, image, and test results.
        self.gesture_template = Template('''
            <tr>
                <td><table>
                    <tr>
                        <h3> $gesture_name.$variation </h3>
                        <h5> $prompt </h5>
                    </tr>
                    <tr>
                        <img src="data:image/png;base64,\n$image"
                            alt="$filename" width="%d" height="%d" />
                    </tr>
                </table></td>
                <td><table>
                    $vlogs
                </table></td>
            </tr>
        ''' % (image_width, image_height))

        self.validator_template =  Template('''
            <tr>
<pre><span style="color:$color"><b>$name</b></span>
$details
    criteria: $criteria
<span style="color:$color"><b>score: $score</b></span></pre>
            </tr>
        ''')

        self.detail_template =  Template('<tr><h5> $detail </h5></tr>')
        self._fill_doc()

    def _html_head(self):
        """Fill the head of an html document."""
        head = '\n'.join(['<!DOCTYPE html>', '<html>', '<body>'])
        return head

    def _html_tail(self):
        """Fill the tail of an html document."""
        tail = '\n'.join(['</body>', '</html>'])
        return tail

    def _fill_doc(self):
        """Fill in fields into the doc."""
        self.doc = Template(self.doc.safe_substitute(head=self._html_head(),
                                                     tail=self._html_tail()))

    def get_score_color(self, score):
        """Present the score in different colors."""
        for s, c in self.score_colors:
            if score >= s:
                return c

    def _insert_details(self, details):
        details_content = []
        for detail in details:
            details_content.append(' ' * 4 + detail.strip())
        return '<br>'.join(details_content)

    def _insert_vlog(self, vlog):
        """Insert a single vlog."""
        score=vlog.get_score()
        vlog_content = self.validator_template.safe_substitute(
                name=vlog.get_name(),
                details=self._insert_details(vlog.get_details()),
                criteria=vlog.get_criteria(),
                color=self.get_score_color(score),
                score=score)
        return vlog_content

    def _insert_vlogs(self, vlogs):
        """Insert multiple vlogs."""
        vlogs_content = []
        for vlog in vlogs:
            vlogs_content.append(self._insert_vlog(vlog))
        return '<hr>'.join(vlogs_content)

    def insert_gesture(self, glog, image, image_filename, vlogs):
        """Insert glog, image, and vlogs."""
        vlogs_content = self._insert_vlogs(vlogs)
        gesture = self.gesture_template.safe_substitute(
                gesture_name=glog.get_name(),
                variation=glog.get_variation(),
                prompt=glog.get_prompt(),
                image=image,
                filename=image_filename,
                vlogs=vlogs_content)
        self.gestures.append(gesture)

    def get_doc(self):
        gestures = ''.join(self.gestures)
        new_table = self.table.safe_substitute(gestures=gestures)
        new_doc = self.doc.safe_substitute(logs=new_table)
        return new_doc


class ReportHtml:
    """Firmware Report in html format."""

    def __init__(self, filename, screen_size, touchpad_window_size,
                 score_colors):
        self.html_filename = filename
        self.screen_size = screen_size
        self.image_width = self.screen_size[0] * 0.5
        touchpad_width, touchpad_height = touchpad_window_size
        self.image_height = self.image_width / touchpad_width * touchpad_height
        self.doc = TemplateHtml(self.image_width, self.image_height,
                                score_colors)
        self._reset_content()
        self.log_dict = {}
        self.log_dict[VLOG.DICT] = {}
        self.log_dict[VLOG.GV_LIST] = []

    def __del__(self):
        self.stop()

    def stop(self):
        """Close the file."""
        with open(self.html_filename, 'w') as report_file:
            report_file.write(self.doc.get_doc())
        # Make a copy to /tmp so that it could be viewed in Chrome.
        tmp_copy = os.path.join(conf.docroot,
                                os.path.basename(self.html_filename))
        copy_cmd = 'cp %s %s' % (self.html_filename, tmp_copy)
        common_util.simple_system(copy_cmd)

        # Dump the logs to a json file
        log_file_root = os.path.splitext(self.html_filename)[0]
        log_file_name = os.extsep.join([log_file_root, 'log'])
        with open(log_file_name, 'w') as log_file:
            json.dump(self.log_dict, log_file)

    def _reset_content(self):
        self.glog = firmware_log.GestureLog()
        self.encoded_image=''
        self.image_filename=''
        self.vlogs = []

    def _get_content(self):
        return [self.glog, self.encoded_image, self.image_filename, self.vlogs]

    def _encode_base64(self, filename):
        """Encode a file in base 64 format."""
        if not os.path.isfile(filename):
            return None
        encoded = urllib.quote(open(filename, "rb").read().encode("base64"))
        return encoded

    def reset_logs(self):
        "Reset the details of vlogs."
        for vlog in self.vlogs:
            vlog.reset()

    def _insert_log_dict(self, glog, vlogs):
        """Insert the glog and vlogs key value pair into the log dictionary."""
        glog_key = str([glog.get_name(), glog.get_variation()])
        if self.log_dict[VLOG.DICT].get(glog_key) is None:
            self.log_dict[VLOG.DICT][glog_key] = {}
        for vlog in vlogs:
            vname = vlog.get_name()
            if self.log_dict[VLOG.DICT][glog_key].get(vname) is None:
                self.log_dict[VLOG.DICT][glog_key][vname] = []
            self.log_dict[VLOG.DICT][glog_key][vname].append(vlog.get_score())

        if glog_key not in self.log_dict[VLOG.GV_LIST]:
            self.log_dict[VLOG.GV_LIST].append(glog_key)

    def flush(self):
        """Flush the current gesture including gesture log, image and
        validator logs.
        """
        content = self._get_content()
        if all(content):
            self.doc.insert_gesture(*content)
            self._insert_log_dict(self.glog, self.vlogs)
            self.reset_logs()
            self._reset_content()

    def insert_image(self, filename):
        """Insert an image into the document."""
        self.encoded_image = self._encode_base64(filename)
        self.image_filename = filename

    def insert_result(self, text):
        """Insert the text into the document."""
        self.result += text

    def insert_gesture_log(self, log):
        """Update the gesture log."""
        self.glog.update(log)

    def insert_validator_logs(self, logs):
        """Update the validator logs."""
        self.vlogs = logs
