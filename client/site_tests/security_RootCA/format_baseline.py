#!/usr/bin/env python
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import re


def dump_baseline(baseline):
  """Pretty dumps baseline as a JSON string."""
  dump = json.dumps(baseline, indent=4, ensure_ascii=False,
                    sort_keys=True, separators=(',', ': ')).encode('utf-8')
  # Replace leading spaces with tabs.
  with_tabs = re.sub(r'\n +', lambda match: '\n\t', dump)
  # Put values on a separate line.
  with_newlines = re.sub(r': (?!{)', lambda match: ':\n\t\t', with_tabs)
  return with_newlines


if __name__ == '__main__':
  with open('./baseline.json', 'r+') as fp:
    baseline = json.load(fp)
    formatted = dump_baseline(baseline)
    fp.seek(0)
    fp.write(formatted)
    fp.truncate()
