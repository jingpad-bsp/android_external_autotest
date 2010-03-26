# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, shutil, time
from autotest_lib.client.bin import test, utils

def get_pids(program_name):
    """
    Collect a list of pids for all the instances of a program.

    @param program_name the name of the program
    @return list of pids
    """
    pidlist = utils.system_output("pgrep -f \'%s\'" % program_name)
    return pidlist.splitlines()


def get_number_of_logical_cpu():
    """
    From /proc/stat/.

    @return number of logic cpu
    """
    ret = utils.system_output("cat /proc/stat | grep ^cpu[0-9+] | wc -l")
    return int(ret)


def get_utime_stime(pids):
    """
    Snapshot the sum of utime and the sum of stime for a list of processes.

    @param pids a list of pid
    @return [sum_of_utime, sum_of_stime]
    """
    timelist = [0, 0]
    for p in pids:
        statFile = file("/proc/%s/stat" % p, "r")
        T = statFile.readline().split(" ")[13:15]
        statFile.close()
        for i in range(len(timelist)):
            timelist[i] = timelist[i] + int(T[i])
    return timelist


def get_cpu_usage(duration, time):
    """
    Calculate cpu usage based on duration and time on cpu.

    @param duration
    @param time on cpu
    @return cpu usage
    """
    return float(time) / float(duration * get_number_of_logical_cpu())


def setup_playground(src, dst, optionfile):
    """
    Setup playground files.

    @param src path
    @param dst path
    @param optionfile
    """
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(src, dst)
    utils.run('chown chronos %s -R' % dst)

    dst_path= '/home/chronos/.Google/'
    opt_path= os.path.join(dst_path, 'Google Talk Plugin')
    dst_opt = os.path.join(opt_path, 'options')
    utils.run('mkdir -p \'%s\'' % opt_path)
    utils.run('cp -f %s \'%s\'' % (optionfile, dst_opt))
    utils.run('chown chronos \'%s\' -R' % dst_path)
    utils.run('chmod o+r+w \'%s\'' % dst_opt)


def cleanup_playground(playground, testdone=False):
    """
    Cleanup playground files.

    @param playground path
    @param testdone
    """
    utils.run('pkill chrome', ignore_status=True)
    time.sleep(10)
    utils.run('pkill GoogleTalkPlugin', ignore_status=True)
    time.sleep(10)
    utils.run('rm -f /tmp/tmp.log', ignore_status=True)
    if testdone:
        shutil.rmtree(playground)

    # Delete previous browser state if any
    shutil.rmtree('/home/chronos/.config/chromium', ignore_errors=True)
    shutil.rmtree('/home/chronos/.config/google-chrome', ignore_errors=True)

