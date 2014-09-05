#!/usr/bin/python

import getpass
import smtplib
import subprocess
import sys

import common  # pylint: disable-msg=W0611
from autotest_lib.site_utils.lib import infra

TESTING = False

print 'Pulling servers...'
SCHEDULERS = infra.sam_servers()
DRONES = infra.drone_servers()
ALL_SERVERS = SCHEDULERS.union(DRONES)
EXTRAS = infra.extra_servers()
TEST_INSTANCE = infra.test_instance()

# List of deployment actions that can be requested, in the order
# in which they'll be executed.
DEPLOY_ACTIONS = [
    ('sync', ALL_SERVERS.union(EXTRAS), 'cd /usr/local/autotest ; '
                                         'repo sync'),
    ('build_externals', ALL_SERVERS, 'cd /usr/local/autotest ; '
                                      './utils/build_externals.py'),
    ('test_importer', SCHEDULERS, 'cd /usr/local/autotest ; '
                                   './utils/test_importer.py'),
    ('migrate', SCHEDULERS, 'cd /usr/local/autotest ; '
                             './database/migrate.py sync'),
    ('afe', SCHEDULERS, 'cd /usr/local/autotest ; '
                    './utils/compile_gwt_clients.py -c autotest.AfeClient'),
    ('tko', SCHEDULERS, 'cd /usr/local/autotest ; '
                    './utils/compile_gwt_clients.py -c autotest.TkoClient'),
    ('apache', SCHEDULERS, 'sudo service apache2 restart'),
    ('scheduler', SCHEDULERS, 'sudo service scheduler restart'),
    ('host_scheduler', SCHEDULERS, 'sudo service host-scheduler restart'),
    ('suite_scheduler', {'cautotest'},
                            'sudo service suite-scheduler restart'),
    ('gs_offloader', DRONES, 'sudo service gs_offloader restart ; '
                              'sudo service gs_offloader_s restart'),
    ('stats_poller', {'chromeos-mcp'}, 'sudo service stats-poller restart'),
]


def update_sources():
    print '\nUpdating checkout...'
    subprocess.check_call('git fetch', shell=True)
    start = subprocess.check_output('git ls-remote cros prod',
                    shell=True).split()[0]
    end = subprocess.check_output('git ls-remote cros master',
                    shell=True).split()[0]
    return start, end


def get_deployment_actions(start, end, extra_actions):
    actions = subprocess.check_output(
                        'git log %s..%s | grep DEPLOY= | '
                        'sed "s/DEPLOY=//" | tr "\n-" ",_"' %
                                  (start, end), shell=True).split(',')
    action_set = set([x.strip() for x in actions if x])
    # Always sync.
    action_set.add('sync')
    action_set = action_set.union(set(extra_actions))
    valid_actions = set([deploy[0] for deploy in DEPLOY_ACTIONS])
    unknowns = action_set - valid_actions
    if unknowns:
        raise Exception('Unknown deploy actions: %s' % list(unknowns))
    return [deploy for deploy in DEPLOY_ACTIONS
                          if deploy[0] in action_set]


def pre_push_test():
    print '\nRunning cbf test...'
    if not TESTING:
        infra.execute_command(TEST_INSTANCE, '~/update_autotest')
        print infra.execute_command(TEST_INSTANCE,
                                    'cd /usr/local/autotest ;'
                                    './site_utils/test_push.py')
    else:
        print '    would test on %s' % TEST_INSTANCE


def rebase_prod_branch():
    print '\nPushing prod...'
    if not TESTING:
        subprocess.check_call('git rebase cros/master prod', shell=True)
        subprocess.check_call('git push cros prod:prod', shell=True)
    else:
        print '    testing - skip push'


def run_deployment_actions(action_list):
    print '\nDeploying...'
    summary_list = []
    for deploy, servers, action in action_list:
        for server in servers:
            print '%s $ %s' % (server, action)
            if not TESTING:
                infra.execute_command(server, action)
            summary_list.append('%s %s' % (server, deploy))
    return summary_list


EMAIL_TEMPLATE = """\
Subject: push to prod %(start)s..%(end)s
From: %(user)s <%(usermail)s>
To: ChromeOS Lab Infrastructure <chromeos-lab-infrastructure@google.com>

%(changes)s
%(actions)s
"""

def send_email(start, end, summary_list):
    print '\nSend e-mail...'

    changes = subprocess.check_output(
                  'git log %s..%s --oneline' % (start, end),
                  shell=True)
    user = getpass.getuser()
    usermail = '%s@google.com' % user

    email_message = EMAIL_TEMPLATE % dict(
            start=start[:7], end=end[:7], changes=changes,
            user=user, usermail=usermail,
            actions='\n'.join(summary_list))
    print email_message
    if not TESTING:
        smtp = smtplib.SMTP('localhost')
        smtp.sendmail(usermail,
                      ['chromeos-lab-infrastructure@google.com'],
                      email_message)


def main(argv):
    start, end = update_sources()
    action_list = get_deployment_actions(start, end, argv)
    pre_push_test()
    rebase_prod_branch()
    summary_list = run_deployment_actions(action_list)
    send_email(start, end, summary_list)


if __name__ == '__main__':
  main(sys.argv[1:])
