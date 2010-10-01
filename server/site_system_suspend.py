#!/usr/bin/python

"""Tell system to suspend, and resume some number of seconds later.

Use the RTC to generate a wakeup some number of seconds into the
future, then go to sleep.  Note that this module is not aware of
the actual time when the system will suspend.  Depending on other
system activities, there may be several seconds between when this
script runs until when the system actually goes to sleep.  In fact
that time may be after the wakeup has been scheduled, and the
system may never wake up!  It is up to the caller to make prudent
decisions as to upper bound of delay before going to sleep, and to
choose a wakeup time greater than this interval.
"""

import os, re, subprocess, sys
import rtc, sys_power

time_to_sleep = 30
if len(sys.argv) > 1:
    time_to_sleep = int(sys.argv[1])

if len(sys.argv) > 2:
    after_command = ' '.join(sys.argv[2:])
else:
    after_command = None

rtc.set_wake_alarm(rtc.get_seconds() + time_to_sleep)

# We want output from suspend_to_ram to go to stderr so that
# tests that depend on the output of after_command won't have
# their output polluted
saveout = os.dup(sys.stdout.fileno())
os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
sys_power.suspend_to_ram()
os.dup2(saveout, sys.stdout.fileno())

if after_command:
    os.system(after_command)
