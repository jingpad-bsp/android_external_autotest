{% comment %}
Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
Use of this source code is governed by a BSD-style license that can be
found in the LICENSE file.

This template describes the configuration file for each individual perf graph.
{% endcomment %}

var Config = {
  // Test title.
  'title': "{{ test_name }}",

  // Link to the source code for the test.
  'source': "http://chrome-svn/viewvc/chrome-internal/" +
            "trunk/data/page_cycler/moz/start.html?revision=HEAD",

  // Link to svn repository viewer; two revision numbers will be appended in
  // the form "123:456".
  'changeLinkPrefix': "http://chromeos-images/diff/report?",

  // Builder name.
  'builder': "chrome Release - Full",

  // Builder link.
  'builderLink': "http://build.chromium.org/buildbot/waterfall/" +
                 "waterfall?builder=chrome%%20Release%%20-%%20Full"
};
