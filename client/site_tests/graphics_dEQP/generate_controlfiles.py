#!/usr/bin/env python

"""
This script generates autotest control files for dEQP. It supports
1) Generate control files for tests with Passing expectations.
2) Generate control files to run tests that are not passing.
3) Decomposing a test into shards. Ideally shard_count is chosen such that
   each shard will run less than 1 minute. It mostly makes sense in
   combination with "hasty".
"""
import os
from collections import namedtuple
# Use 'sudo pip install enum34' to install.
from enum import Enum
# Use 'sudo pip install jinja2' to install.
from jinja2 import Template

Test = namedtuple('Test', 'filter, suite, shards, time, hasty, tag, test_file')


ATTRIBUTES_BVT_CQ = (
    'suite:deqp, suite:graphics_per-day, suite:graphics_system, suite:bvt-cq')
ATTRIBUTES_BVT_PB = (
    'suite:deqp, suite:graphics_per-day, suite:graphics_system, '
    'suite:bvt-perbuild'
)
ATTRIBUTES_DAILY = 'suite:deqp, suite:graphics_per-day, suite:graphics_system'

class Suite(Enum):
    none = 1
    daily = 2
    bvtcq = 3
    bvtpb = 4

test_file_folder = '/usr/local/deqp/master/'
BVT_MASTER_FILE = '/usr/local/autotest/tests/graphics_dEQP/master/bvt.txt'
GLES2_MASTER_FILE = os.path.join(test_file_folder, 'gles2-master.txt')
GLES3_MASTER_FILE = os.path.join(test_file_folder, 'gles3-master.txt')
GLES31_MASTER_FILE = os.path.join(test_file_folder, 'gles31-master.txt')
VK_MASTER_FILE = os.path.join(test_file_folder, 'vk-master.txt')

tests = [
    Test('bvt',                    Suite.bvtcq, shards=1,  hasty=False, time='FAST',     tag='bvt',           test_file=BVT_MASTER_FILE),
    Test('dEQP-GLES2-master',      Suite.daily, shards=1,  hasty=False, time='LENGTHY',  tag='gles2-master',  test_file=GLES2_MASTER_FILE),
    Test('dEQP-GLES2-master',      Suite.bvtpb, shards=10, hasty=True,  time='FAST',     tag='gles2-master',  test_file=GLES2_MASTER_FILE),
    Test('dEQP-GLES2.accuracy',    Suite.bvtcq, shards=1,  hasty=False, time='FAST',     tag=None,            test_file=None),
    Test('dEQP-GLES2.capability',  Suite.bvtcq, shards=1,  hasty=False, time='FAST',     tag=None,            test_file=None),
    Test('dEQP-GLES2.info',        Suite.bvtcq, shards=1,  hasty=False, time='FAST',     tag=None,            test_file=None),
    Test('dEQP-GLES2.stress',      Suite.daily, shards=1,  hasty=False, time='LONG',     tag=None,            test_file=None),
    Test('dEQP-GLES3.accuracy',    Suite.bvtcq, shards=1,  hasty=False, time='FAST',     tag=None,            test_file=None),
    Test('dEQP-GLES3-master',      Suite.daily, shards=1,  hasty=False, time='LENGTHY',  tag='gles3-master',  test_file=GLES3_MASTER_FILE),
    Test('dEQP-GLES3-master',      Suite.bvtpb, shards=10, hasty=True,  time='FAST',     tag='gles3-master',  test_file=GLES3_MASTER_FILE),
    Test('dEQP-GLES3.info',        Suite.bvtcq, shards=1,  hasty=False, time='FAST',     tag=None,            test_file=None),
    Test('dEQP-GLES3.performance', Suite.daily, shards=1,  hasty=False, time='LONG',     tag=None,            test_file=None),
    Test('dEQP-GLES3.stress',      Suite.daily, shards=1,  hasty=False, time='LONG',     tag=None,            test_file=None),
    Test('dEQP-GLES31-master',     Suite.daily, shards=1,  hasty=False, time='LENGTHY',  tag='gles31-master', test_file=GLES31_MASTER_FILE),
    Test('dEQP-GLES31-master',     Suite.bvtpb, shards=10, hasty=True,  time='FAST',     tag='gles31-master', test_file=GLES31_MASTER_FILE),
    Test('dEQP-GLES31.info',       Suite.bvtcq, shards=1,  hasty=False, time='FAST',     tag=None,            test_file=None),
    Test('dEQP-GLES31.stress',     Suite.none,  shards=1,  hasty=False, time='LONG',     tag=None,            test_file=None),
    Test('dEQP-VK-master',         Suite.none,  shards=1,  hasty=False, time='LENGTHY',  tag='vk-master',     test_file=VK_MASTER_FILE),
    Test('dEQP-VK-master',         Suite.daily, shards=10, hasty=True,  time='FAST',     tag='vk-master',     test_file=VK_MASTER_FILE),
    Test('dEQP-VK.api',            Suite.none,  shards=1,  hasty=True,  time='LONG',     tag=None,            test_file=None),
    Test('dEQP-VK.api.smoke',      Suite.bvtcq, shards=1,  hasty=False, time='FAST',     tag=None,            test_file=None),
    Test('dEQP-VK.binding_model',  Suite.none,  shards=1,  hasty=True,  time='LONG',     tag=None,            test_file=None),
    Test('dEQP-VK.glsl',           Suite.none,  shards=1,  hasty=True,  time='LONG',     tag=None,            test_file=None),
    Test('dEQP-VK.info',           Suite.bvtcq, shards=1,  hasty=False, time='FAST',     tag=None,            test_file=None),
    Test('dEQP-VK.pipeline',       Suite.none,  shards=1,  hasty=True,  time='LONG',     tag=None,            test_file=None),
    Test('dEQP-VK.spirv_assembly', Suite.none,  shards=1,  hasty=True,  time='SHORT',    tag=None,            test_file=None),
]

CONTROLFILE_TEMPLATE = Template(
"""\
# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Please do not edit this file! It has been created by generate_controlfiles.py.

NAME = '{{testname}}'
AUTHOR = 'chromeos-gfx'
PURPOSE = 'Run the drawElements Quality Program test suite.'
CRITERIA = 'All of the individual tests must pass.'
ATTRIBUTES = '{{attributes}}'
TIME = '{{time}}'
TEST_CATEGORY = 'Functional'
TEST_CLASS = 'graphics'
TEST_TYPE = 'client'
DOC = \"\"\"
This test runs the drawElements Quality Program test suite.
\"\"\"
job.run_test('graphics_dEQP',{% if tag != None %}
             tag = '{{tag}}',{% endif %}
             opts = args + [
                 {% if test_file == None %}'filter={{filter}}',
                 'subset_to_run={{subset}}',
                 {% else %}'test_names_file={{test_file}}',
                 {% endif %}'hasty={{hasty}}',
                 'shard_number={{shard}}',
                 'shard_count={{shards}}'
             ])"""
    )

#Unlike the normal version it batches many tests in a single run
#to reduce testing time. Unfortunately this is less robust and
#can lead to spurious failures.


def get_controlfilename(test, shard=0):
    return 'control.%s' % get_name(test, shard)


def get_attributes(test):
    if test.suite == Suite.bvtcq:
        return ATTRIBUTES_BVT_CQ
    if test.suite == Suite.bvtpb:
        return ATTRIBUTES_BVT_PB
    if test.suite == Suite.daily:
        return ATTRIBUTES_DAILY
    return ''


def get_time(test):
    return test.time


def get_name(test, shard):
    name = test.filter.replace('dEQP-', '', 1).lower()
    if test.hasty:
        name = '%s.hasty' % name
    if test.shards > 1:
        name = '%s.%d' % (name, shard)
    return name


def get_testname(test, shard=0):
    return 'graphics_dEQP.%s' % get_name(test, shard)


def write_controlfile(filename, content):
    print 'Writing %s.' % filename
    with open(filename, 'w+') as f:
        f.write(content)


def write_controlfiles(test):
    attributes = get_attributes(test)
    time = get_time(test)

    for shard in xrange(0, test.shards):
        testname = get_testname(test, shard)
        filename = get_controlfilename(test, shard)
        content = CONTROLFILE_TEMPLATE.render(
            testname=testname,
            attributes=attributes,
            time=time,
            filter=test.filter,
            subset='Pass',
            hasty=test.hasty,
            shard=shard,
            shards=test.shards,
            test_file=test.test_file,
            tag=test.tag
        )
        write_controlfile(filename, content)


def main():
    for test in tests:
        write_controlfiles(test)

if __name__ == "__main__":
    main()
