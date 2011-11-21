#!/bin/sh
# Intermediate setup script for Autotest scheduler. Called by
# /etc/init.d/autotest when starting.  Ensures ssh-agent is setup properly then
# invokes the normal monitor_db_babysitter.

BASE_DIR=/usr/local/autotest
SOURCE_DIR="/usr/local/google/home/chromeos-test/chromeos/chromeos/src"
TEST_KEY="scripts/mod_for_test_scripts/ssh_keys/testing_rsa"
SSH_AGENT_FILE=$HOME/.ssh/agent.$HOSTNAME

cd /tmp

ssh-add -l > /dev/null 2>&1
if [ $? != 0 ]; then
   if [ -f "${SSH_AGENT_FILE}" ]; then
     # Copy the existing agent stuff into the environment
     . "${SSH_AGENT_FILE}"
   fi
fi # again determine if ssh-agent is running properly
ssh-add -l > /dev/null 2>&1
if [ $? != 0 ]; then
   # start ssh-agent, and put stuff into the environment
   ssh-agent | grep -v "^echo Agent pid" > "${SSH_AGENT_FILE}"
   . "${SSH_AGENT_FILE}"

   # add testing key to ssh-agent
   chmod 400 ${SOURCE_DIR}/${TEST_KEY}
   ssh-add ${SOURCE_DIR}/${TEST_KEY}
fi

${BASE_DIR}/scheduler/monitor_db_babysitter
