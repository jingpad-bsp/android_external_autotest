# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import labconfig_data

class LabConfigError(Exception):
  pass


def extract_options(args, options_to_expand):
    """Extracts options_to_expand from args, returns (extracted, remaining).
    Args:
        args:  A list of arguments
        options_to_expand: A container with options to expand (with
          '--' already prepended)
    Returns:
        (dict of extracted options, list of untouched arguments). """

    remaining = []
    extracted = {}
    i = 0
    while i < len(args):
        (option, delimiter, value) = args[i].partition('=')
        if option in options_to_expand and value:
            extracted[option] = value
        elif (option in options_to_expand) and not delimiter:
            extracted[option] = args[i+1]
            i += 1
        else:
            remaining.append(args[i])
        i += 1
    return (extracted, remaining)


def get_test_arguments(args):
    """Extract the --cell= argument from args, return config, rest of args."""

    (extracted, remaining) = extract_options(args, ['--cell'])
    if '--cell' not in extracted:
        raise LabConfigError(
            'Could not find --cell argument.  ' +
            'To specify a cell, pass --args=--cell=foo to run_remote_tests')

    if extracted['--cell'] not in labconfig_data.CELLS:
        raise LabConfigError('Could not find cell %s, valid cells are %s' %
                             (extracted['--cell'], labconfig_data.CELLS.keys()))

    return (labconfig_data.CELLS[extracted['--cell']], remaining)


def get_test_config(args):
    """Return only a test config (ignoring the remaining args)."""
    return get_test_arguments(args)[0]
