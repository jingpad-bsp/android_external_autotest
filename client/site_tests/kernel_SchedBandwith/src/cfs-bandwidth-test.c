//
// Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
//
// cfs-bandwidth-test
//
// This program places itself into a CFS CPU bandwidth quota cgroup
// normally used for background Chrome renderers, and then starts up
// a separate thread to consume all possible CPU (effectively a "while 1"
// loop), and then after an interval, causes the thread to terminate.
//
// It uses the cpu.stats file in the cgroup in order to report the amount
// of periods in which there was an opportunity to throttle the process,
// the number of actual periods in which throttling occurred, and the
// number of ms of CPU time which would have otherwise gone to the
// throttled process.
//
// Typically run as:
//         % cfs-bandwidth-test         # run for 30 seconds
// or:
//         % cfs-bandwidth-test 90      # run for 90 seconds
//
// The python test wrapper for autotest relies on the default interval.
//
#include <fcntl.h>
#include <libgen.h>
#include <pthread.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sysexits.h>
#include <time.h>
#include <unistd.h>

// Configuration
#define RUN_TIME_DEFAULT_SECONDS    30  // default time to run
#define RUN_TIME_MIN_SECONDS        2   // minimum allowable user time to run
#define CGROUP_DIRECTORY    "/sys/fs/cgroup/cpu/chrome_renderers/background/"

// Enable debugging by setting to 1.
#define DEBUG 0


// Our test loop.  Run for a period of time consuming all CPU until we are
// killed via pthread_kill.
volatile int keep_running = 1;

void *
test_busyloop(void *arg)
{
    while(keep_running)
        continue;

    return NULL;
}


// Alarm handler; this function exists to kill the thread, then return
// control to the main() for status reporting of the test results.
void
handler_alarm(int signal, siginfo_t *siginfo, void *ucontext)
{
    keep_running = 0;
}

// Process stats line into values
void
stats_process(char *buf_stats, long long *periodsp, long long *throttledp,
    long long *throttled_timep)
{
    char *char_pointer;

    // Raw read buffer; convert NLs to spaces.
    for (char_pointer = buf_stats; *char_pointer != 0; char_pointer++)
        if (*char_pointer == '\n')
            *char_pointer = ' ';
    sscanf(buf_stats,
           "nr_periods %lld nr_throttled %lld throttled_time %lld",
           periodsp, throttledp, throttled_timep);
}



// Test program; runs test for 30 seconds or user specified interval, and
// exits, printing test statistics.
int
main(int ac, char *av[])
{
    int duration_seconds = RUN_TIME_DEFAULT_SECONDS;
    char *name_program = basename(av[0]);
    char buf_pid[1024];                     // PID as a string
    char buf_stats_before[1024];            // multiple lines of stats
    char buf_stats_after[1024];             // multiple lines of stats
    pthread_t thread_test;                  // Thread ID for test thread
    struct sigaction sa;
    time_t start_time;
    int fd_tasks;
    int fd_stats;
    long long base_periods, base_throttled, base_time;
    long long end_periods, end_throttled, end_time;

    // Simple argument parse with count check.
    switch(ac) {
    case 1:     // no argument
        break;
    case 2:     // non-default seconds
        duration_seconds = atoi(av[1]);
        if (duration_seconds >= RUN_TIME_MIN_SECONDS)
            break;
        // FALLSTHROUGH

    default:
        fprintf(stderr, "usage: %s [seconds]\n", name_program);
        fprintf(stderr, "       seconds = runtime, >= %d\n",
                RUN_TIME_MIN_SECONDS);
        exit(EX_USAGE);
    }

    // Set up an alarm handler to kill the test thread before anything else.
    memset(&sa, 0, sizeof(sa));
    sa.sa_sigaction = handler_alarm;
    sa.sa_flags = SA_RESETHAND;
    if (sigaction(SIGALRM, &sa, NULL)) {
        perror("sigaction");
        exit(EX_OSERR);
    }

    // Set up a task desriptor so we can add our task
    if ((fd_tasks = open(CGROUP_DIRECTORY "tasks", O_WRONLY)) == -1) {
        perror("open: " CGROUP_DIRECTORY "tasks");
        exit(EX_OSFILE);
    }

    // Set up a stats desriptor to collect our stats when we are done
    if ((fd_stats = open(CGROUP_DIRECTORY "cpu.stat", O_RDONLY)) == -1) {
        perror("open: " CGROUP_DIRECTORY "cpu.stat");
        exit(EX_OSFILE);
    }

    // Add our task to the CPU-limited cgroup.
    sprintf(buf_pid, "%d", getpid());

    // Seek to the end, since the O_APPEND open flag doesn't work on the
    // tasks pseudo-file.
    lseek(fd_tasks, SEEK_END, 0);
    if (write(fd_tasks, buf_pid, strlen(buf_pid)) != strlen(buf_pid)) {
        perror("write: " CGROUP_DIRECTORY "tasks");
        exit(EX_IOERR);
    }

#if DEBUG
    // Report duration.
    printf("RUNNING: duration %d seconds\n", duration_seconds);
#endif

    // Retrieve pre-test stats.  Put everthing on one line for later parsing.
    // Explicit seek works around an update issue if there are other processes
    // entering or leaving the background cgroup while the test is running,
    // e.g. Chrome windows.
    if (lseek(fd_stats, SEEK_SET, 0) == (off_t)-1) {
        perror("lseek: " CGROUP_DIRECTORY "cpu.stat");
        exit(EX_IOERR);
    }
    if (read(fd_stats, buf_stats_before, sizeof(buf_stats_before)) <= 0) {
        perror( "read: " CGROUP_DIRECTORY "cpu.stat");
        exit(EX_IOERR);
    }
    stats_process(buf_stats_before, &base_periods, &base_throttled, &base_time);
#if DEBUG
    printf("BEFORE: %s\n", buf_stats_before);
#endif

    // Wait for the clock to tick 2 times to actually start the program close
    // to a tick boundary.  Two ticks are used to cover first time setup cost
    // for some implementations of the time() call.
    start_time = time(NULL) + 2;
    while (start_time > time(NULL))
        continue;

    // Run the test thread, which will eat all CPU unless bounded by the
    // cgroup.
    if (pthread_create(&thread_test, NULL, &test_busyloop, NULL)) {
        perror("pthread_create");
        exit(EX_SOFTWARE);
    }

    // Stop the process when we get to the specified number of elapsed
    // seconds.  This is inexact, but close enough if the system is in a
    // relatively quiescent state.
    alarm(duration_seconds);
    pause();

    // Retrieve post-test stats.  Put everthing on one line for later parsing.
    if (lseek(fd_stats, SEEK_SET, 0) == (off_t)-1) {
        perror("lseek: " CGROUP_DIRECTORY "cpu.stat");
        exit(EX_IOERR);
    }
    if (read(fd_stats, buf_stats_after, sizeof(buf_stats_after)) <= 0) {
        perror( "read: " CGROUP_DIRECTORY "cpu.stat");
        exit(EX_IOERR);
    }
    stats_process(buf_stats_after, &end_periods, &end_throttled, &end_time);
#if DEBUG
    printf("AFTER: %s\n", buf_stats_after);
#endif

    // Report number of periods for the test, number of periods throttled
    // for the test, and the amount of time throttled in ms.  The amount
    // of time throttled is less useful, since it isn't in wall time, but
    // we have it so report it anyway.
    printf("%lld %lld %lld\n",
           end_periods - base_periods,
           end_throttled - base_throttled,
           (end_time - base_time) / 1000000LL);

    exit(EX_OK);
}
