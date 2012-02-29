# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import optparse
import sys
import subprocess
import time

def daemonize(pid_file_path):
    """
    Borrowed from:
    http://www.jejik.com/articles/2007/02/a_simple_unix_linux_daemon_in_python/

    do the UNIX double-fork magic, see Stevens' "Advanced
    Programming in the UNIX Environment" for details (ISBN 0201563177)
    http://www.erlenstar.demon.co.uk/unix/faq_2.html#SEC16
    """
    try:
        pid = os.fork()
        if pid > 0:
            # exit first parent
            sys.exit(0)
    except OSError, e:
        print("fork #1 failed: %d (%s)\n" % (e.errno, e.strerror))
        sys.exit(1)

    # decouple from parent environment
    os.chdir("/")
    os.setsid()
    os.umask(0)

    # do second fork
    try:
        pid = os.fork()
        if pid > 0:
            # exit from second parent
            sys.exit(0)
    except OSError, e:
        print("fork #2 failed: %d (%s)\n" % (e.errno, e.strerror))
        sys.exit(1)


    pid = str(os.getpid())
    f = open(pid_file_path, 'w')
    f.write('%s\n' % pid)
    f.close()

    # redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()
    si = file('/dev/null', 'r')
    so = file('/dev/null', 'a+')
    se = file('/dev/null', 'a+', 0)
    os.dup2(si.fileno(), sys.stdin.fileno())
    os.dup2(so.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())

    # Print the output of syndetect to a file
    f = open('/tmp/workfile', 'a')
    while True:
        # By design we want to run forever, we expect the device will be kernel
        # paniced.
        command = ('echo -n "rescan" > '
                   '/sys/devices/platform/i8042/serio2/drvctl')
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
        result = process.communicate()[0]
        f.write(result)
        f.write('\n')
        time.sleep(1)
    f.close()


def main():
    parser = optparse.OptionParser()
    parser.add_option('-f', '--pidfile', dest='pid_file_path',
                      help='file path to write the pid', metavar='FILE',
                      default='/tmp/forever_pid.txt')
    (options, args) = parser.parse_args()
    daemonize(options.pid_file_path)


if __name__ == '__main__':
  main()

