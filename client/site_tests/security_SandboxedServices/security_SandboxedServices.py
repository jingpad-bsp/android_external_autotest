# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import csv
import logging
import os

from collections import namedtuple

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils


PS_FIELDS = (
    'pid',
    'ppid',
    'comm:32',
    'euser:%(usermax)d',
    'ruser:%(usermax)d',
    'egroup:%(groupmax)d',
    'rgroup:%(groupmax)d',
    'ipcns',
    'mntns',
    'netns',
    'pidns',
    'userns',
    'utsns',
    'args',
)
# These fields aren't available via ps, so we have to get them indirectly.
# Note: Case is significant as the fields match the /proc/PID/status file.
# Note: Order is significant as it matches order in the /proc/PID/status file.
STATUS_FIELDS = (
    'CapInh',
    'CapPrm',
    'CapEff',
    'CapBnd',
    'Seccomp',
)
PsOutput = namedtuple("PsOutput",
                      ' '.join([field.split(':')[0].lower()
                                for field in PS_FIELDS + STATUS_FIELDS]))

# Constants that match the values in /proc/PID/status Seccomp field.
# See `man 5 proc` for more details.
SECCOMP_MODE_DISABLED = '0'
SECCOMP_MODE_STRICT = '1'
SECCOMP_MODE_FILTER = '2'
# For human readable strings.
SECCOMP_MAP = {
    SECCOMP_MODE_DISABLED: 'disabled',
    SECCOMP_MODE_STRICT: 'strict',
    SECCOMP_MODE_FILTER: 'filter',
}


class security_SandboxedServices(test.test):
    """Enforces sandboxing restrictions on the processes running
    on the system.
    """

    version = 1


    def get_running_processes(self):
        """Returns a list of running processes as PsOutput objects."""

        usermax = utils.system_output("cut -d: -f1 /etc/passwd | wc -L",
                                      ignore_status=True)
        groupmax = utils.system_output('cut -d: -f1 /etc/group | wc -L',
                                       ignore_status=True)
        # Even if the names are all short, make sure we have enough space
        # to hold numeric 32-bit ids too (can come up with userns).
        usermax = max(int(usermax), 10)
        groupmax = max(int(groupmax), 10)
        fields = {
            'usermax': usermax,
            'groupmax': groupmax,
        }
        ps_cmd = ('ps --no-headers -ww -eo ' +
                  (','.join(PS_FIELDS) % fields))
        ps_fields_len = len(PS_FIELDS)

        output = utils.system_output(ps_cmd)
        logging.debug('output of ps:\n%s', output)

        # Fill in fields that `ps` doesn't support but are in /proc/PID/status.
        cmd = (
            "awk '$1 ~ \"^(Pid|%s):\" "
            "{printf \"%%s \", $NF; if ($1 == \"%s:\") printf \"\\n\"}'"
            " /proc/[1-9]*/status"
        ) % ('|'.join(STATUS_FIELDS), STATUS_FIELDS[-1])
        # Processes might exit while awk is running, so ignore its exit status.
        status_output = utils.system_output(cmd, ignore_status=True)
        status_data = dict(line.split(None, 1)
                           for line in status_output.splitlines())
        logging.debug('output of awk:\n%s', status_output)

        # Now merge the two sets of process data.
        missing_status_fields = [None] * len(STATUS_FIELDS)
        running_processes = []
        for line in output.splitlines():
            # crbug.com/422700: Filter out zombie processes.
            if '<defunct>' in line:
                continue

            fields = line.split(None, ps_fields_len - 1)
            pid = fields[0]
            if pid in status_data:
                status_fields = status_data[pid].split()
            else:
                status_fields = missing_status_fields
            running_processes.append(PsOutput(*fields + status_fields))

        return running_processes


    def load_baseline(self):
        """The baseline file lists the services we know and
        whether (and how) they are sandboxed.
        """

        def load(path):
            """Load the baseline out of |path| and return it.

            @param path: The baseline to load.
            """
            logging.info('Loading baseline %s', path)
            reader = csv.DictReader(open(path))
            return dict((d['exe'], d) for d in reader
                        if not d['exe'].startswith('#'))

        baseline_path = os.path.join(self.bindir, 'baseline')
        ret = load(baseline_path)

        board = utils.get_current_board()
        baseline_path += '.' + board
        if os.path.exists(baseline_path):
            ret.update(load(baseline_path))

        return ret


    def load_exclusions(self):
        """The exclusions file lists running programs
        that we don't care about (for now).
        """

        exclusions_path = os.path.join(self.bindir, 'exclude')
        return set(line.strip() for line in open(exclusions_path)
                   if not line.startswith('#'))


    def dump_services(self, running_services, minijail_processes):
        """Leaves a list of running services in the results dir
        so that we can update the baseline file if necessary.

        @param running_services: list of services to be logged.
        @param minijail_processes: list of Minijail processes used to log how
        each running service is sandboxed.
        """

        csv_file = csv.writer(open(os.path.join(self.resultsdir,
                                                "running_services"), 'w'))

        for service in running_services:
            service_minijail = ""

            if service.ppid in minijail_processes:
                launcher = minijail_processes[service.ppid]
                service_minijail = launcher.args.split("--")[0].strip()

            row = [service.comm, service.euser, service.args, service_minijail]
            csv_file.writerow(row)


    def run_once(self):
        """Inspects the process list, looking for root and sandboxed processes
        (with some exclusions). If we have a baseline entry for a given process,
        confirms it's an exact match. Warns if we see root or sandboxed
        processes that we have no baseline for, and warns if we have
        baselines for processes not seen running.
        """

        baseline = self.load_baseline()
        exclusions = self.load_exclusions()
        running_processes = self.get_running_processes()

        kthreadd_pid = -1

        init_process = None
        running_services = {}
        minijail_processes = {}

        # Filter running processes list
        for process in running_processes:
            exe = process.comm

            if exe == "kthreadd":
                kthreadd_pid = process.pid
                continue
            elif exe == 'init':
                init_process = process
                continue

            # Don't worry about kernel threads
            if process.ppid == kthreadd_pid:
                continue

            if exe in exclusions:
                continue

            # Remember minijail0 invocations
            if exe == "minijail0":
                minijail_processes[process.pid] = process
                continue

            running_services[exe] = process

        # Find differences between running services and baseline
        services_set = set(running_services.keys())
        baseline_set = set(baseline.keys())

        new_services = services_set.difference(baseline_set)
        stale_baselines = baseline_set.difference(services_set)

        # Check baseline
        sandbox_delta = []
        for exe in services_set.intersection(baseline_set):
            process = running_services[exe]

            # If the process is not running as the correct user
            if process.euser != baseline[exe]["euser"]:
                logging.error('%s: bad user: wanted "%s" but got "%s"',
                              exe, baseline[exe]['euser'], process.euser)
                sandbox_delta.append(exe)
                continue

            # If the process is not running as the correct group
            if process.egroup != baseline[exe]['egroup']:
                logging.error('%s: bad group: wanted "%s" but got "%s"',
                              exe, baseline[exe]['egroup'], process.egroup)
                sandbox_delta.append(exe)
                continue

            # Check the various sandbox settings.
            if (baseline[exe]['pidns'] == 'Yes' and
                    process.pidns == init_process.pidns):
                logging.error('%s: missing pid ns usage', exe)
                sandbox_delta.append(exe)
            elif (baseline[exe]['caps'] == 'Yes' and
                  process.capeff == init_process.capeff):
                logging.error('%s: missing caps usage', exe)
                sandbox_delta.append(exe)
            elif (baseline[exe]['filter'] == 'Yes' and
                  process.seccomp != SECCOMP_MODE_FILTER):
                logging.error('%s: missing seccomp usage: wanted %s (%s) but '
                              'got %s (%s)', exe, SECCOMP_MODE_FILTER,
                              SECCOMP_MAP[SECCOMP_MODE_FILTER], process.seccomp,
                              SECCOMP_MAP.get(process.seccomp, '???'))
                sandbox_delta.append(exe)

        # Save current run to results dir
        self.dump_services(running_services.values(), minijail_processes)

        if len(stale_baselines) > 0:
            logging.warn('Stale baselines: %r', stale_baselines)

        if len(new_services) > 0:
            logging.warn('New services: %r', new_services)

            # We won't complain about new non-root services (on the assumption
            # that they've already somewhat sandboxed things), but we'll fail
            # with new root services (on the assumption they haven't done any
            # sandboxing work).  If they really need to run as root, they can
            # update the baseline to whitelist it.
            new_root_services = [x for x in new_services
                                 if running_services[x].euser == 'root']
            if new_root_services:
                logging.error('New services are not allowed to run as root, '
                              'but these are: %r', new_root_services)
                sandbox_delta.extend(new_root_services)

        if len(sandbox_delta) > 0:
            logging.error('Failed sandboxing: %r', sandbox_delta)
            raise error.TestFail("One or more processes failed sandboxing")
