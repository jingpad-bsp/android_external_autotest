# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A module handling the logs."""


class GestureLog:
    """A class to handle the logs related with a gesture."""
    NAME = 'gesture_name'
    VARIATION = 'gesture_variation'
    PROMPT = 'gesture_prompt'

    def __init__(self):
        self.log = {self.NAME: None,
                    self.VARIATION: None,
                    self.PROMPT: None}

    def key_list(self):
        return [self.NAME, self.VARIATION, self.PROMPT]

    def _insert(self, key, msg):
        """Insert a message with the specified key."""
        self.log[key] = msg

    def update(self, glog):
        """Update the gesture log."""
        self.log.update(glog.log)

    def insert_name(self, msg):
        """Insert the gesture name."""
        self._insert(self.NAME, msg)

    def insert_variation(self, msg):
        """Insert the gesture variation."""
        self._insert(self.VARIATION, msg)

    def insert_prompt(self, msg):
        """Insert the prompt."""
        self._insert(self.PROMPT, msg)

    def get_name(self):
        """Get the gesture name."""
        return self.log[self.NAME]

    def get_variation(self):
        """Get the gesture variation."""
        return self.log[self.VARIATION]

    def get_prompt(self):
        """Get the prompt."""
        return self.log[self.PROMPT]

    def get_log(self):
        """Get the log."""
        return self.log


class ValidatorLog:
    """A class to handle the logs reported by validators."""
    NAME = 'validator_name'
    DETAILS = 'validator_details'
    CRITERIA = 'validator_criteria'
    SCORE = 'validator_score'
    ERROR = 'error'

    def __init__(self):
        self.log = {self.NAME: None,
                    self.DETAILS: [],
                    self.CRITERIA: None,
                    self.SCORE: None,
                    self.ERROR: None}

    def key_list(self):
        return [self.NAME, self.DETAILS, self.CRITERIA, self.SCORE, self.ERROR]

    def reset(self):
        self.log[self.DETAILS] = []

    def _insert(self, key, msg):
        """Insert a message with the specified key."""
        if key == self.DETAILS:
            self.log[self.DETAILS].append(msg)
        else:
            self.log[key] = msg

    def insert_name(self, msg):
        """Insert the name of the validator."""
        self._insert(self.NAME, msg)

    def insert_details(self, msg):
        """Insert a detailed message."""
        self._insert(self.DETAILS, msg)

    def insert_criteria(self, msg):
        """Insert the criteria string."""
        self._insert(self.CRITERIA, msg)

    def insert_score(self, score):
        """Insert a score."""
        self._insert(self.SCORE, score)

    def insert_error(self, msg):
        """Insert an error message."""
        self._insert(self.ERROR, msg)

    def get_name(self):
        """Get the name of the validator."""
        return self.log[self.NAME]

    def get_details(self):
        """Get the detailed message."""
        return self.log[self.DETAILS]

    def get_criteria(self):
        """Get the criteria string."""
        return self.log[self.CRITERIA]

    def get_score(self):
        """Get the score."""
        return self.log[self.SCORE]

    def get_error(self):
        """Get the error message."""
        return self.log[self.ERROR]

    def get_log(self):
        """Get the log."""
        return self.log
