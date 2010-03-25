# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

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

