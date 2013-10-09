# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module for obtaining Chrome OS board related info."""


import ConfigParser
import os


_BOARD_CONFIG_FILE = os.path.join(os.path.dirname(__file__),
                                  'board_config.ini')


class BoardError(BaseException):
    """Exception related to board info handling."""
    pass


class BoardInfo(object):
    """Provides reference information about known Chrome OS boards.

    The raw data is pulled from a .ini file at the current directory.

    """
    def __init__(self):
        self._board_config = None

    def initialize(self):
        """Read board config."""
        self._board_config = ConfigParser.ConfigParser()
        try:
            self._board_config.readfp(open(_BOARD_CONFIG_FILE))
        except IOError, e:
            raise BoardError('failed to load config file: %s' %
                             (_BOARD_CONFIG_FILE, e))


    def _get_attr(self, board, attr):
        """Returns an attribute for a given board.

        @param board: the name of the board (e.g. 'x86-alex')
        @param attr: specific attribute to return

        @return The value of the given attribute of the given board, in its raw
                (string) form, or None if not defined for this board.

        @raise BoardError: if board is unknown

        """
        try:
            return self._board_config.get(board, attr)
        except ConfigParser.NoSectionError:
            raise BoardError('board not found (%s)' % board)
        except ConfigParser.NoOptionError:
            return None


    def get_board_names(self):
        """Returns the list of board names."""
        return self._board_config.sections()


    def get_fsi_releases(self, board):
        """Returns the list of active FSI releases (string) of a given board.

        Returns None is no FSI releases were defined for this board.

        @raise BoardError: if board is not known
        """
        fsi_releases = self._get_attr(board, 'fsi_releases')
        return map(str.strip, fsi_releases.split(',')) if fsi_releases else None
