# -*- coding: utf-8 -*-

# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Guide the user to perform gestures. Record and validate the gestures."""

import fcntl
import os
import subprocess
import sys
import time

import common_util
import firmware_log
import firmware_utils
import fuzzy
import mini_color
import test_conf as conf
import validators

sys.path.append('/usr/local/autotest/bin/input')
import input_device


class TestFlow:
    """Guide the user to perform gestures. Record and validate the gestures."""

    def __init__(self, device_geometry, device, win, parser, output):
        self.device_geometry = device_geometry
        self.device = device
        self.device_node = self.device.device_node
        self.firmware_version = self.device.get_firmware_version()
        self.board = firmware_utils.get_board()
        self.output = output
        self._get_record_cmd()
        self.win = win
        self.win.set_prompt(self._get_prompt_result())
        self.parser = parser
        self.packets = None
        self.gesture_file_name = None
        self.prefix_space = self.output.get_prefix_space()
        self.scores = []
        self.gesture_list = conf.get_gesture_list()
        self._get_all_gesture_variations()
        self.init_flag = False
        self.system_device = self._non_blocking_open(self.device_node)
        self.evdev_device = input_device.InputEvent()
        self.screen_shot = firmware_utils.ScreenShot(self.geometry_str)

    def __del__(self):
        self.system_device.close()

    def _non_blocking_open(self, filename):
        """Open the file in non-blocing mode."""
        fd = open(filename)
        fcntl.fcntl(fd, fcntl.F_SETFL, os.O_NONBLOCK)
        return fd

    def _non_blocking_read(self, dev, fd):
        """Non-blocking read on fd."""
        try:
            dev.read(fd)
            event = (dev.tv_sec, dev.tv_usec, dev.type, dev.code, dev.value)
        except Exception, e:
            event = None
        return event

    def _reopen_system_device(self):
        """Close the device and open a new one."""
        self.system_device.close()
        self.system_device = open(self.device_node)
        self.system_device = self._non_blocking_open(self.device_node)

    def _get_prompt_next(self):
        """Prompt for next gesture."""
        prompt = ("Press SPACE to save this file and go to next test,\n"
                  "      'm'   to save this file and record again,\n"
                  "      'd'   to delete this file and try again,\n"
                  "      'x'   to discard this file and exit.")
        return prompt

    def _get_prompt_result(self):
        """Prompt to see test result through timeout callback."""
        prompt = ("Perform the gesture now.\n"
                  "See the test result on the right after finger lifted.")
        return prompt

    def _get_prompt_result_for_keyboard(self):
        """Prompt to see test result using keyboard."""
        prompt = ("Press SPACE to see the test result,\n"
                  "      'd'   to delete this file and try again,\n"
                  "      'x'   to exit.")
        return prompt

    def _get_prompt_no_data(self):
        """Prompt to remind user of performing gestures."""
        prompt = ("You need to perform the specified gestures "
                  "before pressing SPACE.\n")
        return prompt + self._get_prompt_result()

    def _get_record_cmd(self):
        """Get the device event record command."""
        self.record_program = 'mtplot'
        if not common_util.program_exists(self.record_program):
            msg = 'Error: the program "%s" does not exist in $PATH.'
            self.output.print_report(msg % self.record_program)
            exit(1)

        display_name = firmware_utils.get_display_name()
        self.geometry_str = '%dx%d+%d+%d' % self.device_geometry
        format_str = '%s %s -d %s -g %s'
        self.record_cmd = format_str % (self.record_program,
                                        self.device_node,
                                        display_name,
                                        self.geometry_str)
        self.output.print_report('Record program: %s' % self.record_cmd)

    def _span_seq(self, seq1, seq2):
        """Span sequence seq1 over sequence seq2.

        E.g., seq1 = (('a', 'b'), 'c')
              seq2 = ('1', ('2', '3'))
              res = (('a', 'b', '1'), ('a', 'b', '2', '3'),
                     ('c', '1'), ('c', '2', '3'))
        E.g., seq1 = ('a', 'b')
              seq2 = ('1', '2', '3')
              res  = (('a', '1'), ('a', '2'), ('a', '3'),
                      ('b', '1'), ('b', '2'), ('b', '3'))
        E.g., seq1 = (('a', 'b'), ('c', 'd'))
              seq2 = ('1', '2', '3')
              res  = (('a', 'b', '1'), ('a', 'b', '2'), ('a', 'b', '3'),
                      ('c', 'd', '1'), ('c', 'd', '2'), ('c', 'd', '3'))
        """
        to_list = lambda s: list(s) if isinstance(s, tuple) else [s]
        return tuple(tuple(to_list(s1) + to_list(s2)) for s1 in seq1
                                                      for s2 in seq2)

    def span_variations(self, seq):
        """Span the variations of a gesture."""
        if seq is None:
            return (None,)
        elif isinstance(seq[0], tuple):
            return reduce(self._span_seq, seq)
        else:
            return seq

    def _stop(self):
        """Terminate the recording process."""
        self.record_proc.poll()
        # Terminate the process only when it was not terminated yet.
        if self.record_proc.returncode is None:
            self.record_proc.terminate()
            self.record_proc.wait()
        self.output.print_window('')

    def _get_gesture_image_name(self):
        """Get the gesture file base name without file extension."""
        filepath = os.path.splitext(self.gesture_file_name)[0]
        self.gesture_image_name = filepath + '.png'
        return filepath

    def _stop_record_and_post_image(self):
        """Terminate the recording process."""
        self.screen_shot.dump_root(self._get_gesture_image_name())
        self.record_proc.terminate()
        self.record_proc.wait()
        self.win.set_image(self.gesture_image_name)

    def _create_prompt(self, test, variation):
        """Create a color prompt."""
        prompt = test.prompt
        if isinstance(variation, tuple):
            subprompt = reduce(lambda s1, s2: s1 + s2,
                               tuple(test.subprompt[s] for s in variation))
        elif variation is None or test.subprompt is None:
            subprompt = None
        else:
            subprompt = test.subprompt[variation]

        if subprompt is None:
            color_prompt = prompt
            monochrome_prompt = prompt
        else:
            color_prompt = mini_color.color_string(prompt, '{', '}', 'green')
            color_prompt = color_prompt.format(*subprompt)
            monochrome_prompt = prompt.format(*subprompt)

        color_msg_format = mini_color.color_string('\n<%s>:\n%s%s', '<', '>',
                                                   'blue')
        color_msg = color_msg_format % (test.name, self.prefix_space,
                                        color_prompt)
        msg = '%s: %s' % (test.name, monochrome_prompt)

        glog = firmware_log.GestureLog()
        glog.insert_name(test.name)
        glog.insert_variation(variation)
        glog.insert_prompt(monochrome_prompt)

        return (msg, color_msg, glog)

    def _choice_exit(self):
        """Procedure to exit."""
        self._stop()
        if os.path.exists(self.gesture_file_name):
            os.remove(self.gesture_file_name)
            self.output.print_report(self.deleted_msg)

    def _stop_record_and_rm_file(self):
        """Stop recording process and remove the current gesture file."""
        self._stop()
        if os.path.exists(self.gesture_file_name):
            os.remove(self.gesture_file_name)
            self.output.print_report(self.deleted_msg)

    def _create_gesture_file_name(self, gesture, variation):
        """Create the gesture file name based on its variation."""
        if variation is None:
            gesture_name = gesture.name
        else:
            if type(variation) is tuple:
                name_list = [gesture.name,] + list(variation)
            else:
                name_list = [gesture.name, variation]
            gesture_name = '.'.join(name_list)

        basename = conf.filename.sep.join([
                gesture_name,
                firmware_utils.get_board(),
                'fw_' + self.firmware_version,
                firmware_utils.get_current_time_str()])
        filename = '.'.join([basename, conf.filename.ext])
        return filename

    def _add_scores(self, new_scores):
        """Add the new scores of a single gesture to the scores list."""
        if new_scores is not None:
            self.scores += new_scores

    def _final_scores(self, scores):
        """Print the final score."""
        # Note: conf.score_aggregator uses a function in fuzzy module.
        final_score = eval(conf.score_aggregator)(scores)
        self.output.print_report('\nFinal score: %s\n' % str(final_score))

    def _handle_user_choice_save_after_parsing(self, next_gesture):
        """Handle user choice for saving the parsed gesture file."""
        self.output.print_window('')
        self.output.print_report(self.saved_msg)
        self._add_scores(self.new_scores)
        self.win.set_prompt(self._get_prompt_result())
        self.output.report_html.insert_image(self.gesture_image_name)
        self.output.report_html.flush()
        if self._pre_setup_this_gesture_variation(next_gesture=next_gesture):
            # There are more gestures.
            self._setup_this_gesture_variation()
        else:
            # No more gesture.
            self._final_scores(self.scores)
            self.output.stop()
            self.output.report_html.stop()
            self.win.stop()
        self.packets = None

    def _handle_user_choice_discard_after_parsing(self):
        """Handle user choice for discarding the parsed gesture file."""
        self.output.print_window('')
        self.output.report_html.reset_logs()
        self.win.set_prompt(self._get_prompt_result())
        self._setup_this_gesture_variation()
        self.packets = None

    def _handle_user_choice_exit_after_parsing(self):
        """Handle user choice to exit after the gesture file is parsed."""
        self._stop_record_and_rm_file()
        self.output.stop()
        self.output.report_html.stop()
        self.win.stop()

    def _handle_user_choice_validate_before_parsing(self):
        """Handle user choice for validating before gesture file is parsed."""
        # Parse the device events. Make sure there are events.
        self.packets = self.parser.parse_file(self.gesture_file_name)
        if self.packets:
            # Validate this gesture and get the results.
            (self.new_scores, msg_list, vlogs) = validators.validate(
                    self.packets, self.gesture, self.variation)
            self.output.print_window(msg_list)
            self.output.buffer_report(msg_list)
            self.output.report_html.insert_validator_logs(vlogs)
            self.gesture_file.close()
            self.win.set_prompt(self._get_prompt_next())
            print self._get_prompt_next()
            self._stop_record_and_post_image()
        else:
            self.win.set_prompt(self._get_prompt_no_data(), color='red')

    def _handle_user_choice_exit_before_parsing(self):
        """Handle user choice to exit before the gesture file is parsed."""
        self.gesture_file.close()
        self._handle_user_choice_exit_after_parsing()

    def _is_parsing_gesture_file_done(self):
        """Is parsing the gesture file done?"""
        return self.packets is not None

    def user_choice_callback(self, widget, event):
        """A callback to handle the key pressed by the user.

        This is the primary GUI event-driven method handling the user input.
        """
        choice = event.string
        if self._is_parsing_gesture_file_done():
            # Save this gesture file and go to next gesture.
            if choice in (' ', '\r'):
                self._handle_user_choice_save_after_parsing(next_gesture=True)
            # Save this file and perform the same gesture again.
            elif choice == 'm':
                self._handle_user_choice_save_after_parsing(next_gesture=False)
            # Discard this file and perform the gesture again.
            elif choice == 'd':
                self._handle_user_choice_discard_after_parsing()
            # The user wants to exit.
            elif choice == 'x':
                self._handle_user_choice_exit_after_parsing()
            # The user presses any wrong key.
            else:
                self.win.set_prompt(self._get_prompt_next(), color='red')
        else:
            # Save this gesture file and go to next gesture.
            if choice in (' ', '\r'):
                self._handle_user_choice_validate_before_parsing()
            # Discard this file and perform the gesture again.
            elif choice == 'd':
                self._handle_user_choice_discard_after_parsing()
            elif choice == 'x':
                self._handle_user_choice_exit_before_parsing()
            # The user presses any wrong key.
            else:
                self.win.set_prompt(self._get_prompt_result(), color='red')

    def _get_all_gesture_variations(self):
        """Get all variations for all gestures."""
        gesture_variations_list = []
        for gesture in self.gesture_list:
            variations = self.span_variations(gesture.variations)
            for variation in variations:
                gesture_variations_list.append((gesture, variation))
        self.gesture_variations = iter(gesture_variations_list)

    def gesture_timeout_callback(self):
        """A callback watching whether a gesture has timed out."""
        if self.gesture_continues_flag:
            self.gesture_continues_flag = False
            return True
        else:
            self.win.set_input_focus()
            self._handle_user_choice_validate_before_parsing()
            self.win.remove_event_source(self.gesture_file_watch_tag)
            self.win.set_input_focus()
            return False

    def gesture_file_watch_callback(self, fd, condition, evdev_device):
        """A callback to watch the device input."""
        # Read the device node continuously until end
        event = True
        while event:
            event = self._non_blocking_read(evdev_device, fd)

        self.gesture_continues_flag = True
        if (not self.gesture_begins_flag):
            self.gesture_begins_flag = True
            self.win.register_timeout_add(self.gesture_timeout_callback,
                                          self.gesture.timeout)
        return True

    def init_gesture_setup_callback(self, widget, event):
        """A callback to set up environment before a user starts a gesture."""
        if not self.init_flag:
            self.init_flag = True
            self._pre_setup_this_gesture_variation()
            self._setup_this_gesture_variation()

    def _pre_setup_this_gesture_variation(self, next_gesture=True):
        """Get gesture, variation, filename, prompt, etc."""
        if next_gesture:
            gesture_variation = next(self.gesture_variations, None)
            if gesture_variation is None:
                return False
            self.gesture, self.variation = gesture_variation

        self.gesture_file_name = os.path.join(self.output.log_dir,
                self._create_gesture_file_name(self.gesture, self.variation))
        (msg, color_msg, glog) = self._create_prompt(self.gesture,
                                                     self.variation)
        self.win.set_gesture_name(msg)
        self.output.report_html.insert_gesture_log(glog)
        print color_msg
        self.output.print_report(color_msg)
        self.saved_msg = '(saved: %s)\n' % self.gesture_file_name
        self.deleted_msg = '(deleted: %s)\n' % self.gesture_file_name

        return True

    def _setup_this_gesture_variation(self):
        """Fork a new process for mtplot. Add io watch for the gesture file."""
        self.gesture_file = open(self.gesture_file_name, 'w')
        self.record_proc = subprocess.Popen(self.record_cmd.split(),
                                            stdout=self.gesture_file)

        # Set input focus to the firmware window rather than mtplot
        time.sleep(0.2)
        self.win.set_input_focus()

        # Watch if data come in to the monitored file.
        self.gesture_begins_flag = False
        self._reopen_system_device()
        self.gesture_file_watch_tag = self.win.register_io_add_watch(
                self.gesture_file_watch_callback, self.system_device,
                self.evdev_device)
