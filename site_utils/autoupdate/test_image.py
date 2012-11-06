# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module for discovering Chrome OS test images and payloads."""


import subprocess


# A string indicating a zip-file boundary within a URI path. This string must
# end with a '/', in order for standard basename code to work correctly for
# zip-encapsulated paths.
ZIPFILE_BOUNDARY = '//'


class TestImageError(BaseException):
    pass


def gs_ls(uri_pattern):
    """Returns a list of URIs that match a given pattern.

    @param uri_pattern: a GS URI pattern, may contain wildcards

    @return A list of URIs matching the given pattern.

    """
    gs_cmd = ['gsutil', 'ls', uri_pattern]
    output = subprocess.Popen(gs_cmd, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE).stdout
    return [path.rstrip() for path in output if path]


def find_payload_uri(board, release, branch, delta=False,
                     single=False):
    """Finds test payloads corresponding to a given board/release.

    @param board: the platform name (string)
    @param release: the release version (string), without milestone and
           attempt/build counters
    @param branch: the release's branch name
    @param delta: if true, seek delta payloads to the given release
    @param single: if true, expect a single match and return it, otherwise
           None

    @return A (possibly empty) list of URIs, or a single (possibly None) URI if
            |single| is True.

    @raise TestImageError if an error has occurred.

    """
    payload_uri_list = gs_ls(
            'gs://chromeos-image-archive/%s-release/%s-%s/%s' %
            (board, branch, release,
             ('chromeos_*_%s-%s*_%s_delta_dev.bin' %
              (branch, release, board))
             if delta
             else ('chromeos_%s-%s*_%s_full_dev.bin' %
                   (branch, release, board))))

    if single:
        payload_uri_list_len = len(payload_uri_list)
        if payload_uri_list_len == 0:
            return None
        elif payload_uri_list_len != 1:
            raise TestImageError('unexpected number of results (%d instead '
                                 'of 1)' % payload_uri_list_len)
        return payload_uri_list[0]

    return payload_uri_list


def find_image_uri(board, release, branch):
    """Returns a URI to a test image.

    @param board: the platform name (string)
    @param release: the release version (string), without milestone and
           attempt/build counters
    @param branch: the release's branch name

    @return A URI to the desired image if found, None otherwise. It will most
            likely be a file inside an image archive (image.zip), in which case
            we'll be using ZIPFILE_BOUNDARY ('//') to denote a zip-encapsulated
            file, for example:
            gs://chromeos-image-archive/.../image.zip//chromiumos_test_image.bin

    @raise TestImageError if an error has occurred.

    """
    image_archive_uri_list = gs_ls('gs://chromeos-image-archive/%s-release/'
                                   '%s-%s/image.zip' % (board, branch, release))

    image_archive_uri_list_len = len(image_archive_uri_list)
    if image_archive_uri_list_len == 0:
        return None
    elif image_archive_uri_list_len != 1:
        raise TestImageError('unexpected number of results (%d > 1)' %
                             image_archive_uri_list_len)

    return (image_archive_uri_list[0] + ZIPFILE_BOUNDARY +
            'chromiumos_test_image.bin')
