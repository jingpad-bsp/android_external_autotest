#!/usr/bin/python

import subprocess
import smtplib
import getpass

import common  # pylint: disable-msg=W0611
from autotest_lib.site_utils.lib import infra

TESTING = False

print 'Pulling servers...'
SCHEDULERS = infra.sam_servers()
DRONES = infra.drone_servers()
ALL_SERVERS = SCHEDULERS.union(DRONES)
EXTRAS = infra.extra_servers()
TEST_INSTANCE = infra.test_instance()

deploy_actions = {
    'scheduler': (SCHEDULERS, 'sudo service scheduler restart'),
    'host_scheduler': (SCHEDULERS, 'sudo service host-scheduler restart'),
    'suite_scheduler': ({'cautotest'}, 'sudo service suite-scheduler restart'),
    'build_externals': (ALL_SERVERS, 'cd /usr/local/autotest ; '
                                     './utils/build_externals.py'),
    'apache': (SCHEDULERS, 'sudo service apache2 restart'),
    'gs_offloader': (DRONES, 'sudo service gs_offloader restart ; '
                             'sudo service gs_offloader_s restart'),
    'migrate': (SCHEDULERS, 'cd /usr/local/autotest ; '
                            './database/migrate.py sync'),
    'afe': (SCHEDULERS, 'cd /usr/local/autotest ; '
                        './utils/compile_gwt_clients.py -c autotest.AfeClient'),
    'tko': (SCHEDULERS, 'cd /usr/local/autotest ; '
                        './utils/compile_gwt_clients.py -c autotest.TkoClient'),
    'test_importer': (SCHEDULERS, 'cd /usr/local/autotest ; '
                                  './utils/test_importer.py'),
    'stats_poller': ({'chromeos-mcp'}, 'sudo service stats-poller restart'),
    # Re-use deploy mechanism to do repo sync on all servers.
    'sync': (ALL_SERVERS.union(EXTRAS), 'cd /usr/local/autotest ; repo sync'),
}

print 'Updating checkout...'
subprocess.check_call('git fetch', shell=True)
start = subprocess.check_output('git ls-remote cros prod',
                shell=True).split()[0]
end = subprocess.check_output('git ls-remote cros master',
                shell=True).split()[0]
changes = subprocess.check_output('git log %s..%s --oneline' % (start, end),
                shell=True)
deploys = subprocess.check_output('git log %s..%s | grep DEPLOY= | '
                                  "sed s/DEPLOY=// | tr '\n' ','" %
                                  (start, end), shell=True).split(',')
deploys = [x.strip() for x in deploys if x]
# Sync all servers first
deploys.insert(0, 'sync')

unknowns = filter(lambda x: x not in deploy_actions, deploys)
if unknowns:
    raise Exception('Unknown deploy actions: %s' % unknowns)

if not TESTING:
    print 'Running cbf test...'
    infra.execute_command(TEST_INSTANCE, '~/update_autotest')
    print infra.execute_command(TEST_INSTANCE, 'cd /usr/local/autotest ;'
                                               './site_utils/test_push.py')

if not TESTING:
    print 'Pushing prod...'
    subprocess.check_call('git rebase cros/master prod', shell=True)
    subprocess.check_call('git push cros prod:prod', shell=True)

print 'Deploying...'
actions = []
for deploy in deploys:
    servers, action = deploy_actions[deploy]
    for server in servers:
        print '%s $ %s' % (server, action)
        if not TESTING:
            infra.execute_command(server, action)
        actions.append((server, deploy))

user = getpass.getuser()
usermail = '%s@google.com' % user

EMAIL = """\
Subject: push to prod
From: %(user)s <%(usermail)s>
To: ChromeOS Lab Infrastructure <chromeos-lab-infrastructure@google.com>


%(start)s..%(end)s

%(changes)s

%(actions)s
""" % dict(start=start, end=end,
           changes=changes, user=user, usermail=usermail,
           actions='\n'.join(['%s %s' % (x,y) for x, y in actions]))

print EMAIL
smtp = smtplib.SMTP('localhost')
if not TESTING:
    smtp.sendmail(usermail, ['chromeos-lab-infrastructure@google.com'], EMAIL)
