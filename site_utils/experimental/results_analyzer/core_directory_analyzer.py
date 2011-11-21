#!/usr/bin/python


import sys

from operator import itemgetter


def PrintTopN(tag, dict, n):
  sorted_items = sorted(dict.items(), key=itemgetter(1), reverse=True)
  for i in xrange(n):
    print '%s: %sGB, %s, id=%s' % (
        tag,
        sorted_items[i][1]/1024/1024/1024,
        sorted_items[i][1],
        sorted_items[i][0])


def main(argv):
  if len(argv) < 1:
    return

  input_file = argv[1]
  f = open(input_file, 'r')
  lines = f.readlines()
  f.close()

  total_size = 0
  total_core_size = 0

  job_crash_stats = {}
  test_crash_stats = {}
  cores_found = {}
  dup_core_list = set()

  # 3 interesting cases of result nesting observed for core files:
  # size full file path
  # 1179648  ./7010-chromeos-test/172.31.26.147/network_Ping/sysinfo/var/spool/crash/Xorg.20101028.093326.21199.core
  # 16494592 ./6985-chromeos-test/group0/172.31.26.210/graphics_SanAngeles/sysinfo/var/spool/crash/Xorg.20101028.030736.179.core
  # 1867834  ./6990-chromeos-test/group0/netpipe.netpipelarge2/172.31.26.223/netpipe/sysinfo/home/chronos/user/log/chromeos-wm.20101022-021116

  for line in lines:
    if line:
      fields = line.split(' ')
      file_size = int(fields[0])
      total_size += file_size
      full_filename = fields[1].rstrip('\n')
      dirs = full_filename.split('/')

      job = dirs[1].split('-')[0]
      job_crash_stats.setdefault(job, 0)
      job_crash_stats[job] += file_size

      if dirs[3][:3] == '172':
        test = dirs[4]
      else:
        test = dirs[3]
      test_crash_stats.setdefault(test, 0)
      test_crash_stats[test] += file_size

      core_name = dirs[-1]
      if core_name[-1] == '\n':
        print 'newline'
      if core_name.find('core') > -1:
        core_stats = cores_found.setdefault(core_name, [0, 0, ''])
        core_stats[0] += 1
        if core_stats[0] > 1:
          dup_core_list.add(full_filename)
        core_stats[1] += file_size
        core_stats[2] = test
        total_core_size += file_size

  print '---------------------'
  print 'Cores:'
  for key, core_values in cores_found.iteritems():
    print '%s, %s, %s, %sMB' % (
        core_values[0],
        core_values[2],
        key,
        int(core_values[1])/1024/1024)
  print '---------------------'
  print 'Dup Cores:'
  sorted_dups = sorted(list(dup_core_list))
  for one_core in sorted_dups:
    print one_core
  print '---------------------'
  PrintTopN('job', job_crash_stats, 10)
  print '---------------------'
  PrintTopN('test', test_crash_stats, 10)
  print '---------------------'
  print 'Core files: %sGB' % (total_core_size / 1024 / 1024 / 1024)
  print '---------------------'
  print 'All files: %sGB' % (total_size / 1024 / 1024 / 1024)
  print '---------------------'


if __name__ == '__main__':
  main(sys.argv)
