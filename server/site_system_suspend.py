#!/usr/bin/python

"""Tell system to suspend, and resume some number of seconds later."""

import os, re, subprocess, sys
import rtc, sys_power

time_to_sleep = 30
if len(sys.argv) > 1:
    time_to_sleep = int(sys.argv[1])

if len(sys.argv) > 2:
    after_command = ' '.join(sys.argv[2:])
else:
    after_command = None

sys_power.do_suspend(time_to_sleep)

if after_command:
    os.system(after_command)
