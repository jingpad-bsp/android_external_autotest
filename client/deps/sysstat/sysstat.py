#!/usr/bin/python

import os
import common
from autotest_lib.client.bin import utils

version = 1

def setup(tarball, topdir):
    srcdir = os.path.join(topdir, 'src')
    if not os.path.exists(tarball):
        utils.get_file(
            'http://pagesperso-orange.fr/sebastien.godard/sysstat-9.0.6.tar.gz',
            tarball)
    utils.extract_tarball_to_dir(tarball, 'src')
    os.chdir(srcdir)
    utils.configure('--prefix=%s' % topdir)
    utils.system('make')
    os.chdir(topdir)

pwd = os.getcwd()
tarball = os.path.join(pwd, 'sysstat-9.0.6.tar.gz')
utils.update_version(pwd+'/src', False, version, setup, tarball, pwd)
