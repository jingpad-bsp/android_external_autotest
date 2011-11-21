#!/bin/bash

# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# Author: ericli@google.com (Eric Li)
#
# This script will deploy a new gwt autotest server frontend to
# /usr/local/autotest, it assumes all database update and third_party packages
# were setup already.
#
# The user should install apache and mysql server before hand.


SCRIPT_DIR=$(cd $(dirname $0);pwd)
AUTOTEST_TOOLS_DIR=$(cd ${SCRIPT_DIR}/../..;pwd)
REPO_DIR=$(cd ${AUTOTEST_TOOLS_DIR}/../../..;pwd)
AUTOTEST_DIR="${REPO_DIR}/src/third_party/autotest/files"

USR_LOCAL_AUTOTEST="/usr/local/autotest"

sudo mkdir -p ${USR_LOCAL_AUTOTEST}
sudo chown -R ${USER}:$(id -gn) ${USR_LOCAL_AUTOTEST}

# Copy Autotest installation.
cp -fpr ${AUTOTEST_DIR}/* ${USR_LOCAL_AUTOTEST}

# Copy Dashboard files.
mkdir -p ${AUTOTEST_DIR}/utils/dashboard
cp -fpr ${AUTOTEST_TOOLS_DIR}/dashboard ${AUTOTEST_DIR}/utils
cp -fpr ${AUTOTEST_TOOLS_DIR}/dashboard/templates/* ${AUTOTEST_DIR}/frontend/templates/

# Copy private global_config.ini in.
cp -p ${AUTOTEST_TOOLS_DIR}/autotest/global_config.ini ${USR_LOCAL_AUTOTEST}

cp -fpr ${AUTOTEST_TOOLS_DIR}/autotest/syncfiles/* ${USR_LOCAL_AUTOTEST}

sudo rm -f /etc/apache2/sites-enabled/000-default
sudo rm -f /etc/apache2/sites-enabled/001-autotest
sudo ln -s ${USR_LOCAL_AUTOTEST}/apache/conf/apache-conf /etc/apache2/sites-enabled/001-autotest

sudo apt-get install -t extras libapache2-mod-google-sso
sudo rm -f /etc/apache2/mods-enabled/google_sso.load
sudo ln -s /etc/apache2/mods-available/google_sso.load /etc/apache2/mods-enabled/google_sso.load
sudo rm -f /etc/apache2/mods-enabled/rewrite.load
sudo ln -s /etc/apache2/mods-available/rewrite.load /etc/apache2/mods-enabled/rewrite.load
sudo  cp -fp ${AUTOTEST_TOOLS_DIR}/autotest/etc_apache2/apache2.conf /etc/apache2
sudo a2enmod headers

/usr/local/autotest/utils/build_externals.py
${USR_LOCAL_AUTOTEST}/utils/compile_gwt_clients.py -a

# ${USR_LOCAL_AUTOTEST}/frontend/manage.py syncdb
# ${USR_LOCAL_AUTOTEST}/frontend/manage.py syncdb

chmod -R o+r ${USR_LOCAL_AUTOTEST}
find ${USR_LOCAL_AUTOTEST} -type d | xargs chmod o+x
chmod o+x ${USR_LOCAL_AUTOTEST}/tko/*.cgi

sudo apache2ctl restart
