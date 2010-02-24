#!/usr/bin/python

import os
import common
from autotest_lib.client.bin import utils

version = 1

def setup(tarball, topdir):
    srcdir = os.path.join(topdir, 'src')
    utils.extract_tarball_to_dir(tarball, srcdir)
    os.chdir(srcdir)
    # This binary is not necessary and breaks non-x86 autotest builds
    os.remove('contrib/fix_standby')
    utils.system('make')
    utils.system('make binprefix=%s manprefix=%s install' % (topdir, topdir))
    os.chdir(topdir)


# The source is grabbed from
# http://sourceforge.net/projects/hdparm/files/hdparm/hdparm-9.27.tar.gz
pwd = os.getcwd()
tarball = os.path.join(pwd, 'hdparm-9.27.tar.gz')
utils.update_version(pwd+'/src', False, version, setup, tarball, pwd)
