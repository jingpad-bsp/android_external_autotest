# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module provides GUI for touchpad firmware test using GTK."""

import re

import gobject
import gtk
import gtk.gdk
import pango

import firmware_utils
import test_conf as conf


TITLE = "Touchpad Firmware Test"


class BaseFrame(object):
    """A simple base frame class."""
    def __init__(self, label=None, size=None, aspect=False):
        # Create a regular/aspect frame
        self.frame = gtk.AspectFrame() if aspect else gtk.Frame()
        self.frame.set_shadow_type(gtk.SHADOW_ETCHED_OUT)
        self.size = size
        if label:
            self.frame.set_label(label)
            self.frame.set_label_align(0.0, 0.0)
            frame_label = self.frame.get_label_widget()
            markup_str = '<span foreground="%s" size="x-large">%s</span>'
            frame_label.set_markup(markup_str % ('black', label))
        if size:
            width, height = size
            self.frame.set_size_request(width, height)
            if aspect:
                self.frame.set(ratio=(float(width) / height))


class PromptFrame(BaseFrame):
    """A simple frame widget to display the prompt.

    It consists of:
      - A frame
      - a label showing the gesture name
      - a label showing the prompt
      - a label showing the keyboard interactions
    """

    def __init__(self, label=None, size=None):
        super(PromptFrame, self).__init__(label, size)

        # Create a vertical packing box.
        self.vbox = gtk.VBox(False, 0)
        self.frame.add(self.vbox)

        # Create a label to show the gesture name
        self.label_gesture = gtk.Label('Gesture Name')
        self.label_gesture.set_justify(gtk.JUSTIFY_LEFT)
        self.vbox.pack_start(self.label_gesture, True, True, 0)
        # Expand the lable to be wider and wrap the line if necessary.
        if self.size:
            _, label_height = self.label_gesture.get_size_request()
            width, _ = self.size
            label_width = int(width * 0.9)
            self.label_gesture.set_size_request(label_width, label_height)
        self.label_gesture.set_line_wrap(True)

        # Pack a horizontal separator
        self.vbox.pack_start(gtk.HSeparator(), True, True, 0)

        # Create a label to show the prompt
        self.label_prompt = gtk.Label('Prompt')
        self.label_prompt.set_justify(gtk.JUSTIFY_CENTER)
        self.vbox.pack_start(self.label_prompt, True, True, 0)

        # Create a label to show the choice
        self.label_choice = gtk.Label('')
        self.label_choice.set_justify(gtk.JUSTIFY_LEFT)
        self.vbox.pack_start(self.label_choice, True, True, 0)

        # Show all widgets added to this frame
        self.frame.show_all()

    def set_gesture_name(self, string, color='blue'):
        """Set the gesture name in label_gesture."""
        markup_str = '<b><span foreground="%s" size="xx-large"> %s </span></b>'
        self.label_gesture.set_markup(markup_str % (color, string))

    def set_prompt(self, string, color='black'):
        """Set the prompt in label_prompt."""
        markup_str = '<span foreground="%s" size="x-large"> %s </span>'
        self.label_prompt.set_markup(markup_str % (color, string))

    def set_choice(self, string):
        """Set the choice in label_choice."""
        self.label_choice.set_text(string)


class ResultFrame(BaseFrame):
    """A simple frame widget to display the test result.

    It consists of:
      - A frame
      - a label showing the test result
    """

    def __init__(self, label=None, size=None):
        super(ResultFrame, self).__init__(label, size)

        # Create a vertical packing box.
        self.vbox = gtk.VBox(False, 0)
        self.frame.add(self.vbox)

        # Create a label to show the gesture name
        self.result = gtk.Label()
        self.vbox.pack_start(self.result , False, False, 0)

        # Show all widgets added to this frame
        self.frame.show_all()

    def _calc_result_font_size(self):
        """Calculate the font size so that it does not overflow."""
        label_width_in_px, _ = self.size
        font_size = int(float(label_width_in_px) / conf.num_chars_per_row *
                        pango.SCALE)
        return font_size

    def set_result(self, text, color='black'):
        """Set the text in the result label."""
        mod_text = re.sub('<', '&lt;', text)
        mod_text = re.sub('>', '&gt;', mod_text)
        markup_str = '<b><span foreground="%s" size="%d"> %s </span></b>'
        font_size = self._calc_result_font_size()
        self.result.set_markup(markup_str % (color, font_size, mod_text))


class ImageFrame(BaseFrame):
    """A simple frame widget to display the mtplot window.

    It consists of:
      - An aspect frame
      - an image widget showing mtplot
    """

    def __init__(self, label=None, size=None):
        super(ImageFrame, self).__init__(label, size, aspect=True)

        # Use a fixed widget to display the image.
        self.fixed = gtk.Fixed()
        self.frame.add(self.fixed)

        # Create an image widget.
        self.image = gtk.Image()
        self.fixed.put(self.image, 0, 0)

        # Show all widgets added to this frame
        self.frame.show_all()

    def set_from_file(self, filename):
        """Set the image file."""
        self.image.set_from_file(filename)
        self.frame.show_all()


class FirmwareWindow(object):
    """A simple window class to display the touchpad firmware test window."""

    def __init__(self, size=None, prompt_size=None, result_size=None,
                 image_size=None):
        self._upload_choice = False

        # Create a new window
        self.win = gtk.Window(gtk.WINDOW_TOPLEVEL)
        if size:
            self.win_size = size
            self.win.resize(*size)
        self.win.set_title(TITLE)
        self.win.set_border_width(0)

        # Create the prompt frame
        self.prompt_frame = PromptFrame(TITLE, prompt_size)

        # Create the result frame
        self.result_frame = ResultFrame("Test results:", size=result_size)

        # Create the image frame for mtplot
        self.image_frame = ImageFrame(size=image_size)

        # Handle layout below
        self.box0 = gtk.VBox(False, 0)
        self.box1 = gtk.HBox(False, 0)
        # Arrange the layout about box0
        self.win.add(self.box0)
        self.box0.pack_start(self.prompt_frame.frame, True, True, 0)
        self.box0.pack_start(self.box1, True, True, 0)
        # Arrange the layout about box1
        self.box1.pack_start(self.image_frame.frame, True, True, 0)
        self.box1.pack_start(self.result_frame.frame, True, True, 0)

        # Capture keyboard events.
        self.win.add_events(gtk.gdk.KEY_PRESS_MASK | gtk.gdk.KEY_RELEASE_MASK)

        # Set a handler for delete_event that immediately exits GTK.
        self.win.connect("delete_event", self.delete_event)

        # Show all widgets.
        self.win.show_all()

    def register_callback(self, event, callback):
        """Register a callback function for an event."""
        self.win.connect(event, callback)

    def register_timeout_add(self, callback, timeout):
        """Register a callback function for gobject.timeout_add."""
        return gobject.timeout_add(timeout, callback)

    def register_io_add_watch(self, callback, fd, data=None,
                              condition=gobject.IO_IN):
        """Register a callback function for gobject.io_add_watch."""
        if data:
            return gobject.io_add_watch(fd, condition, callback, data)
        else:
            return gobject.io_add_watch(fd, condition, callback)

    def create_key_press_event(self, keyval):
        """Create a key_press_event."""
        event = gtk.gdk.Event(gtk.gdk.KEY_PRESS)
        # Assign current time to the event
        event.time = 0
        event.keyval = keyval
        self.win.emit('key_press_event', event)

    def remove_event_source(self, tag):
        """Remove the registered callback."""
        gobject.source_remove(tag)

    def delete_event(self, widget, event, data=None):
        """A handler to exit the window."""
        self.stop()
        return False

    def set_input_focus(self):
        """Set input focus to this window."""
        x = firmware_utils.SimpleX(TITLE)
        x.set_input_focus()

    def set_gesture_name(self, string, color='blue'):
        """A helper method to set gesture name."""
        self.prompt_frame.set_gesture_name(string, color)

    def set_prompt(self, string, color='black'):
        """A helper method to set the prompt."""
        self.prompt_frame.set_prompt(string, color)

    def set_choice(self, string):
        """A helper method to set the choice."""
        self.prompt_frame.set_choice(string)

    def set_result(self, text):
        """A helper method to set the text in the result."""
        self.result_frame.set_result(text)

    def set_image(self, filename):
        """Set an image in the image frame."""
        self.image_frame.set_from_file(filename)

    def stop(self, upload_choice=False):
        """Quit the window."""
        gtk.main_quit()
        self._upload_choice = upload_choice

    def main(self):
        """Main function of the window."""
        gtk.main()
        return self._upload_choice
