#!/usr/bin/python

import os
import common
from autotest_lib.client.bin import utils

version = 1

def setup(tarball, topdir):
    srcdir = os.path.join(topdir, 'src')
    os.chdir(srcdir)
    utils.make()
    os.chdir(topdir)


pwd = os.getcwd()
utils.update_version(pwd+'/src', True, version, setup, None, pwd)
