# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
This module provides utilities needed to provision and run test on Android
devices.
"""


import logging
import re

import common
from autotest_lib.client.common_lib import global_config


CONFIG = global_config.global_config

def get_config_value_regex(section, regex):
    """Get config values from global config based on regex of the key.

    @param section: Section of the config, e.g., CLIENT.
    @param regex: Regular expression of the key pattern.

    @return: A dictionary of all config values matching the regex. Value is
             assumed to be comma separated, and is converted to a list.
    """
    configs = CONFIG.get_config_value_regex(section, regex)
    result = {}
    for key, value in configs.items():
        match = re.match(regex, key)
        result[match.group(1)] = [v.strip() for v in value.split(',')]
    return result


class AndroidImageFiles(object):
    """A wrapper class for constants and methods related to image files.
    """

    BOOTLOADER = 'bootloader.img'
    RADIO = 'radio.img'
    BOOT = 'boot.img'
    SYSTEM = 'system.img'
    VENDOR = 'vendor.img'

    # Image files not inside the image zip file. These files should be
    # downloaded directly from devserver.
    DEFAULT_STANDALONE_IMAGES = [BOOTLOADER, RADIO]

    # Default image files that are packaged in a zip file, e.g.,
    # shamu-img-123456.zip
    DEFAULT_ZIPPED_IMAGES = [BOOT, SYSTEM, VENDOR]

    # Default image files to be flashed to an Android device.
    DEFAULT_IMAGES = DEFAULT_STANDALONE_IMAGES + DEFAULT_ZIPPED_IMAGES

    # regex pattern for CLIENT/android_standalone_images_[board]. For example,
    # global config can have following config in CLIENT section to indicate that
    # android board `xyz` has following standalone images.
    # ['bootloader_image', 'radio_image'].
    # android_standalone_xyz: bootloader.img,radio.img
    STANDALONE_IMAGES_PATTERN = 'android_standalone_images_(.*)'

    # A dict of board:images for standalone images, can be defined in global
    # config CLIENT/android_standalone_images_[board]
    standalone_images_map = get_config_value_regex('CLIENT',
                                                   STANDALONE_IMAGES_PATTERN)

    # regex pattern for CLIENT/android_standalone_images_[board]. For example,
    # global config can have following config in CLIENT section to indicate that
    # android board `xyz` has following standalone images.
    # ['bootloader_image', 'radio_image'].
    # android_zipped_xyz: bootloader.img,radio.img
    ZIPPED_IMAGES_PATTERN = 'android_zipped_images_(.*)'

    # A dict of board:images for zipped images, can be defined in global
    # config CLIENT/android_zipped_images_[board]
    zipped_images_map = get_config_value_regex('CLIENT', ZIPPED_IMAGES_PATTERN)

    @classmethod
    def get_standalone_images(cls, board):
        """Get a list of standalone image files for given board.

        @param board: Name of the board.

        @return: A list of standalone image files.
        """
        if board in cls.standalone_images_map:
            logging.debug('Found override of standalone image files for board '
                          '%s: %s', board, cls.standalone_images_map[board])
            return cls.standalone_images_map[board]
        else:
            return cls.DEFAULT_STANDALONE_IMAGES


    @classmethod
    def get_zipped_images(cls, board):
        """Get a list of image files from zip_images artifact for given board.

        @param board: Name of the board.

        @return: A list of image files from `zip_images`.
        """
        if board in cls.zipped_images_map:
            logging.debug('Found override of zip image files for board '
                          '%s: %s', board, cls.zipped_images_map[board])
            return cls.zipped_images_map[board]
        else:
            return cls.DEFAULT_ZIPPED_IMAGES


class AndroidArtifacts(object):
    """A wrapper class for constants and methods related to artifacts.
    """

    BOOTLOADER_IMAGE = 'bootloader_image'
    DTB = 'dtb'
    RADIO_IMAGE = 'radio_image'
    TARGET_FILES = 'target_files'
    TEST_ZIP = 'test_zip'
    VENDOR_PARTITIONS = 'vendor_partitions'
    ZIP_IMAGE = 'zip_images'

    # (os, board) = 'artifacts'
    DEFAULT_ARTIFACTS_MAP = {
        ('android', 'default'): [BOOTLOADER_IMAGE, RADIO_IMAGE, ZIP_IMAGE,
                                 TEST_ZIP],
        ('brillo', 'default'):  [ZIP_IMAGE, VENDOR_PARTITIONS],
        ('emulated_brillo', 'default'): [TARGET_FILES, DTB],
    }

    # Default artifacts for Android provision
    DEFAULT_ARTIFACTS_TO_BE_STAGED_FOR_IMAGE = (
            ','.join([BOOTLOADER_IMAGE, RADIO_IMAGE, ZIP_IMAGE, TEST_ZIP]))

    # regex pattern for CLIENT/android_artifacts_[board]. For example, global
    # config can have following config in CLIENT section to indicate that
    # android board `xyz` needs to stage artifacts
    # ['bootloader_image', 'radio_image'] for provision.
    # android_artifacts_xyz: bootloader_image,radio_image
    ARTIFACTS_LIST_PATTERN = 'android_artifacts_(.*)'

    # A dict of board:artifacts, can be defined in global config
    # CLIENT/android_artifacts_[board]
    artifacts_map = get_config_value_regex('CLIENT', ARTIFACTS_LIST_PATTERN)

    @classmethod
    def get_artifacts_for_reimage(cls, board, os='android'):
        """Get artifacts need to be staged for reimage for given board.

        @param board: Name of the board.

        @return: A string of artifacts to be staged.
        """
        if board in cls.artifacts_map:
            logging.debug('Found override of artifacts for board %s: %s', board,
                          cls.artifacts_map[board])
            artifacts = cls.artifacts_map[board]
        elif (os, board) in cls.DEFAULT_ARTIFACTS_MAP:
            artifacts = cls.DEFAULT_ARTIFACTS_MAP[(os, board)]
        else:
            artifacts = cls.DEFAULT_ARTIFACTS_MAP[(os, 'default')]
        return ','.join(artifacts)

