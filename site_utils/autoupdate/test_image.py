# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module for discovering Chrome OS test images and payloads."""

import logging
import os
import re

import common
from autotest_lib.client.common_lib import global_config

try:
  from devserver import gsutil_util
except ImportError:
  # Make this easy for users to automatically import the devserver if not found.
  from autotest_lib.utils import build_externals, external_packages
  tot = external_packages.find_top_of_autotest_tree()
  install_dir = os.path.join(tot, build_externals.INSTALL_DIR)
  build_externals.build_and_install_packages(
      [external_packages.DevServerRepo()], install_dir)
  from devserver import gsutil_util


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
    archive_base = global_config.global_config.get_config_value(
            'CROS', 'image_storage_server')
    archive_base = archive_base.rstrip('/') # Remove any trailing /'s.

    # TODO(garnold) adjustment to -he variant board names; should be removed
    # once we switch to using artifacts from gs://chromeos-images/
    # (see chromium-os:38222)
    board = re.sub('-he$', '_he', board)

    return ARCHIVE_URL_FORMAT % dict(
            archive_base=archive_base, board=board, branch=branch,
            release=release)


def gs_ls(pattern, archive_url, single):
    """Returns a list of URIs that match a given pattern.

    @param pattern: a regexp pattern to match (feeds into re.match).
    @param archive_url: the gs uri where to search (see ARCHIVE_URL_FORMAT).
    @param single: if true, expect a single match and return it.

    @return A list of URIs (possibly an empty list).

    """
    try:
        logging.debug('Searching for pattern %s from url %s', pattern,
                      archive_url)
        uri_list = gsutil_util.GetGSNamesWithWait(
                pattern, archive_url, err_str=__name__, single_item=single,
                timeout=1)
        # Convert to the format our clients expect (full archive path).
        return ['/'.join([archive_url, u]) for u in uri_list]
    except gsutil_util.PatternNotSpecific as e:
        raise TestImageError(str(e))
    except gsutil_util.GSUtilError:
        return []


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
        pattern = '.*_delta_.*'
    else:
        pattern = '.*_full_.*'

    payload_uri_list = gs_ls(pattern, archive_url, single)
    if not payload_uri_list:
        return None if single else []

    return payload_uri_list[0] if single else payload_uri_list


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

    image_archive = gs_ls('image.zip', archive_url, single=True)
    if not image_archive:
        return None

    return (image_archive[0] + ZIPFILE_BOUNDARY + 'chromiumos_test_image.bin')
