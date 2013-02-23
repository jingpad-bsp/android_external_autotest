# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module for discovering Chrome OS test images and payloads."""

import logging
import re
import subprocess

import common
from autotest_lib.client.common_lib import global_config


# A string indicating a zip-file boundary within a URI path. This string must
# end with a '/', in order for standard basename code to work correctly for
# zip-encapsulated paths.
ZIPFILE_BOUNDARY = '//'
ARCHIVE_URL_FORMAT = '%(archive_base)s/%(board)s-release/%(branch)s-%(release)s'


class TestImageError(BaseException):
    """Raised on any error in this module."""
    pass


def _get_archive_url(board, branch, release):
    """Returns the gs archive_url for the respective arguments."""
    # TODO(garnold) adjustment to -he variant board names; should be removed
    # once we switch to using artifacts from gs://chromeos-images/
    # (see chromium-os:38222)
    archive_base = global_config.global_config.get_config_value(
            'CROS', 'image_storage_server')
    archive_base = archive_base.rstrip('/') # Remove any trailing /'s.
    board = re.sub('-he$', '_he', board)
    return ARCHIVE_URL_FORMAT % dict(
            archive_base=archive_base, board=board, branch=branch,
            release=release)


def gs_ls(uri_pattern):
    """Returns a list of URIs that match a given pattern.

    @param uri_pattern: a GS URI pattern, may contain wildcards

    @return A list of URIs matching the given pattern.

    """
    gs_cmd = ['gsutil', 'ls', uri_pattern]
    logging.debug(' '.join(gs_cmd))
    output = subprocess.Popen(gs_cmd, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE).stdout
    return [path.rstrip() for path in output if path]


def find_payload_uri(board, release, branch, delta=False,
                     single=False, archive_url=None):
    """Finds test payloads corresponding to a given board/release.

    @param board: the platform name (string)
    @param release: the release version (string), without milestone and
           attempt/build counters
    @param branch: the release's branch name
    @param delta: if true, seek delta payloads to the given release
    @param single: if true, expect a single match and return it, otherwise
           None
    @param archive_url: Optional archive_url directory to find the payload.

    @return A (possibly empty) list of URIs, or a single (possibly None) URI if
            |single| is True.

    @raise TestImageError if an error has occurred.

    """
    if not archive_url:
        archive_url = _get_archive_url(board, branch, release)

    if delta:
        gs_ls_search = (archive_url + '/chromeos_*_%s-%s*_%s_delta_dev.bin' %
                        (branch, release, board))
    else:
        gs_ls_search = (archive_url + '/chromeos_%s-%s*_%s_full_dev.bin' %
                        (branch, release, board))

    payload_uri_list = gs_ls(gs_ls_search)

    if single:
        payload_uri_list_len = len(payload_uri_list)
        if payload_uri_list_len == 0:
            return None
        elif payload_uri_list_len != 1:
            raise TestImageError('unexpected number of results (%d instead '
                                 'of 1)' % payload_uri_list_len)
        return payload_uri_list[0]

    return payload_uri_list


def find_image_uri(board, release, branch, archive_url=None):
    """Returns a URI to a test image.

    @param board: the platform name (string)
    @param release: the release version (string), without milestone and
           attempt/build counters
    @param branch: the release's branch name
    @param archive_url: Optional archive_url directory to find the payload.

    @return A URI to the desired image if found, None otherwise. It will most
            likely be a file inside an image archive (image.zip), in which case
            we'll be using ZIPFILE_BOUNDARY ('//') to denote a zip-encapsulated
            file, for example:
            gs://chromeos-image-archive/.../image.zip//chromiumos_test_image.bin

    @raise TestImageError if an error has occurred.

    """
    if not archive_url:
        archive_url = _get_archive_url(board, branch, release)

    gs_ls_search = archive_url + '/image.zip'
    image_archive_uri_list = gs_ls(gs_ls_search)

    image_archive_uri_list_len = len(image_archive_uri_list)
    if image_archive_uri_list_len == 0:
        return None
    elif image_archive_uri_list_len != 1:
        raise TestImageError('unexpected number of results (%d > 1)' %
                             image_archive_uri_list_len)

    return (image_archive_uri_list[0] + ZIPFILE_BOUNDARY +
            'chromiumos_test_image.bin')
