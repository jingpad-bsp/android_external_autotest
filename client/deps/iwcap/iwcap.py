#!/usr/bin/python

import os, common
from autotest_lib.client.bin import utils

version = 1

def setup(tarball, topdir):
    srcdir = os.path.join(topdir, 'src')
    utils.extract_tarball_to_dir(tarball, srcdir)
    os.chdir(srcdir)
    utils.system('make BINDIR=%s install' % (topdir))
    os.chdir(topdir)

pwd = os.getcwd()
tarball = os.path.join(pwd, 'iwcap.tar.gz')
utils.update_version(pwd + '/src', False, version, setup, tarball, pwd)
