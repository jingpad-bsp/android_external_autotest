# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Library providing an API to lucifer."""

import os
import logging
import pipes

import common
from autotest_lib.client.bin import local_host
from autotest_lib.client.common_lib import global_config
from autotest_lib.server.hosts import ssh_host

_config = global_config.global_config
_SECTION = 'LUCIFER'

# TODO(crbug.com/748234): Move these to shadow_config.ini
# See also drones.AUTOTEST_INSTALL_DIR
_AUTOTEST_DIR = '/usr/local/autotest'
_JOB_REPORTER_PATH = os.path.join(_AUTOTEST_DIR, 'bin', 'job_reporter')

logger = logging.getLogger(__name__)


def is_lucifer_enabled():
    """Return True if lucifer is enabled in the config."""
    return _config.get_config_value(_SECTION, 'send_jobs_to_lucifer',
                                    type=bool)


def is_enabled_for(level):
    """Return True if lucifer is enabled for the given level.

    @param level: string, e.g. 'PARSING', 'GATHERING'
    """
    if not is_lucifer_enabled():
        return False
    config_level = (_config.get_config_value(_SECTION, 'lucifer_level')
                    .upper())
    return level.upper() == config_level


def is_lucifer_owned(job):
    """Return True if job is already sent to lucifer."""
    return hasattr(job, 'jobhandoff')


def spawn_job_handler(manager, job, autoserv_exit, pidfile_id=None):
    """Spawn job_reporter to handle a job.

    Pass all arguments by keyword.

    @param manager: DroneManager instance
    @param job: Job instance
    @param autoserv_exit: autoserv exit status
    @param pidfile_id: PidfileId instance
    """
    manager = _DroneManager(manager)
    if pidfile_id is None:
        drone = manager.pick_drone_to_use()
    else:
        drone = manager.get_drone_for_pidfile(pidfile_id)
    args = [
            '--run-job-path', _get_run_job_path(),
            '--jobdir', _get_jobdir(),
            '--job-id', str(job.id),
            '--autoserv-exit', str(autoserv_exit),
    ]
    # lucifer_run_job arguments
    results_dir = _results_dir(manager, job)
    args.extend([
            '--',
            '-resultsdir', results_dir,
            '-autotestdir', _AUTOTEST_DIR,
            '-watcherpath', _get_watcher_path(),
    ])
    output_file = os.path.join(results_dir, 'job_reporter_output.log')
    drone.spawn(_JOB_REPORTER_PATH, args, output_file=output_file)


def _get_jobdir():
    return _config.get_config_value(_SECTION, 'jobdir', type=str)


def _get_run_job_path():
    return os.path.join(_get_binaries_path(), 'lucifer_run_job')


def _get_watcher_path():
    return os.path.join(_get_binaries_path(), 'lucifer_watcher')


def _get_binaries_path():
    """Get binaries dir path from config.."""
    return _config.get_config_value(_SECTION, 'binaries_path', type=str)


class _DroneManager(object):
    """Simplified drone API."""

    def __init__(self, old_manager):
        """Initialize instance.

        @param old_manager: old style DroneManager
        """
        self._manager = old_manager

    def get_drone_for_pidfile(self, pidfile_id):
        """Return a drone to use from a pidfile.

        @param pidfile_id: PidfileId instance.
        """
        return _wrap_drone(self._manager.get_drone_for_pidfile_id(pidfile_id))

    def pick_drone_to_use(self, num_processes=1, prefer_ssp=False):
        """Return a drone to use.

        Various options can be passed to optimize drone selection.

        @param num_processes: number of processes the drone is intended
            to run
        @param prefer_ssp: indicates whether drones supporting
            server-side packaging should be preferred.  The returned
            drone is not guaranteed to support it.
        """
        old_drone = self._manager.pick_drone_to_use(
                num_processes=num_processes,
                prefer_ssp=prefer_ssp,
        )
        return _wrap_drone(old_drone)

    def absolute_path(self, path):
        """Return absolute path for drone results.

        The returned path might be remote.
        """
        return self._manager.absolute_path(path)


def _wrap_drone(old_drone):
    """Wrap an old style drone."""
    host = old_drone._host
    if isinstance(host, local_host.LocalHost):
        return LocalDrone()
    elif isinstance(host, ssh_host.SSHHost):
        return RemoteDrone(host)
    else:
        raise TypeError('Drone has an unknown host type')


def _results_dir(manager, job):
    """Return results dir for a job.

    Path may be on a remote host.
    """
    return manager.absolute_path(_working_directory(job))


def _working_directory(job):
    return _get_consistent_execution_path(job.hostqueueentry_set.all())


def _get_consistent_execution_path(execution_entries):
    first_execution_path = execution_entries[0].execution_path()
    for execution_entry in execution_entries[1:]:
        assert execution_entry.execution_path() == first_execution_path, (
            '%s (%s) != %s (%s)' % (execution_entry.execution_path(),
                                    execution_entry,
                                    first_execution_path,
                                    execution_entries[0]))
    return first_execution_path


class Drone(object):
    """Simplified drone API."""

    def spawn(self, path, args, output_file):
        """Spawn an independent process.

        path must be an absolute path.  path may be on a remote machine.
        args is a list of arguments.

        The process is spawned in its own session.  It should not try to
        obtain a controlling terminal.

        The new process will have stdin opened to /dev/null and stdout,
        stderr opened to output_file.

        output_file is a pathname, but how it is interpreted is
        implementation defined, e.g., it may be a remote file.
        """


class LocalDrone(Drone):
    """Local implementation of Drone."""

    def spawn(self, path, args, output_file):
        _spawn(path, [path] + args, output_file)


class RemoteDrone(Drone):
    """Remote implementation of Drone through SSH."""

    def __init__(self, host):
        if not isinstance(host, ssh_host.SSHHost):
            raise TypeError('RemoteDrone must be passed an SSHHost')
        self._host = host

    def spawn(self, path, args, output_file):
        cmd_parts = [path] + args
        safe_cmd = ' '.join(pipes.quote(part) for part in cmd_parts)
        safe_file = pipes.quote(output_file)
        # SSH creates a session for each command, so we do not have to
        # do it.
        self._host.run('%(cmd)s <%(null)s >>%(file)s 2>&1 &'
                       % {'cmd': safe_cmd,
                          'file': safe_file,
                          'null': os.devnull})


def _spawn(path, argv, output_file):
    """Spawn a new process in its own session.

    path must be an absolute path.  The first item in argv should be
    path.

    In the calling process, this function returns on success.
    The forked process puts itself in its own session and execs.

    The new process will have stdin opened to /dev/null and stdout,
    stderr opened to output_file.
    """
    logger.info('Spawning %r, %r, %r', path, argv, output_file)
    assert all(isinstance(arg, basestring) for arg in argv)
    if os.fork():
        return
    os.setsid()
    null_fd = os.open(os.devnull, os.O_RDONLY)
    os.dup2(null_fd, 0)
    os.close(null_fd)
    out_fd = os.open(output_file, os.O_WRONLY | os.O_APPEND | os.O_CREAT)
    os.dup2(out_fd, 1)
    os.dup2(out_fd, 2)
    os.close(out_fd)
    os.execv(path, argv)
