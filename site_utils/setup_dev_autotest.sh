#!/bin/bash
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
set -e

USAGE="Usage: setup_dev_autotest.sh [-p <password>] [-a </path/to/autotest>]"
HELP="${USAGE}\n\n\
Install and configure software needed to run autotest locally.\n\
If you're just working on tests, you do not need to run this.\n\n\
Options:\n\
  -p Desired Autotest DB password\n\
  -a Absolute path to autotest source tree.\n"

AUTOTEST_DIR=
PASSWD=
while getopts ":p:a:h" opt; do
  case $opt in
    a)
      AUTOTEST_DIR=$OPTARG
      ;;
    p)
      PASSWD=$OPTARG
      ;;
    h)
      echo -e "${HELP}" >&2
      exit 0
      ;;
    \?)
      echo "Invalid option: -$OPTARG" >&2
      echo "${USAGE}" >&2
      exit 1
      ;;
    :)
      echo "Option -$OPTARG requires an argument." >&2
      echo "${USAGE}" >&2
      exit 1
      ;;
  esac
done

if [ -z "${PASSWD}" ]; then
  read -s -p "Autotest DB password: " PASSWD
  echo
  if [ -z "${PASSWD}" ]; then
    echo "Empty passwords not allowed." >&2
    exit 1
  fi
  read -s -p "Re-enter password: " PASSWD2
  echo
  if [ "${PASSWD}" != "${PASSWD2}" ]; then
    echo "Passwords don't match." >&2
    exit 1
  fi
fi

if [ -z "${AUTOTEST_DIR}" ]; then
  CANDIDATE=$(dirname "$(readlink -f "$0")" | egrep -o '(/[^/]+)*/files')
  read -p "Enter autotest dir [${CANDIDATE}]: " AUTOTEST_DIR
  if [ -z "${AUTOTEST_DIR}" ]; then
    AUTOTEST_DIR="${CANDIDATE}"
  fi
fi


# Sanity check AUTOTEST_DIR. If it's null, or doesn't exist on the filesystem
# then die.
if [ -z "${AUTOTEST_DIR}" ]; then
  echo "No AUTOTEST_DIR. Aborting script."
  exit 1
fi

if [ ! -d "${AUTOTEST_DIR}" ]; then
  echo "Directory " ${AUTOTEST_DIR} " does not exist. Aborting script."
  exit 1
fi


SHADOW_CONFIG_PATH="${AUTOTEST_DIR}/shadow_config.ini"
echo "Autotest supports local overrides of global configuration through a "
echo "'shadow' configuration file.  Setting one up for you now."
CLOBBER=0
if [ -f ${SHADOW_CONFIG_PATH} ]; then
  clobber=
  while read -n 1 -p "Clobber existing shadow config? [Y/n]: " clobber; do
    echo
    if [[ -z "${clobber}" || $(echo ${clobber} | egrep -qi 'y|n') -eq 0 ]]; then
      break
    fi
    echo "Please enter y or n."
  done
  if [[ "${clobber}" = 'n' || "${clobber}" = 'N' ]]; then
    CLOBBER=1
    echo "Refusing to clobber existing shadow_config.ini."
  else
    echo "Clobbering existing shadow_config.ini."
  fi
fi

CROS_CHECKOUT=$(readlink -f ${AUTOTEST_DIR}/../../../..)

# Create clean shadow config if we're replacing it/creating a new one.
if [ $CLOBBER -eq 0 ]; then
  cat > "${SHADOW_CONFIG_PATH}" <<EOF
[AUTOTEST_WEB]
host: localhost
password: ${PASSWD}
readonly_host: localhost
readonly_user: chromeosqa-admin
readonly_password: ${PASSWD}

[SERVER]
hostname: localhost

[SCHEDULER]
drones: localhost

[CROS]
source_tree: ${CROS_CHECKOUT}
EOF
  echo -e "Done!\n"
fi

echo "Installing needed Ubuntu packages..."
PKG_LIST="mysql-server mysql-common libapache2-mod-wsgi python-mysqldb \
gnuplot apache2-mpm-prefork unzip python-imaging libpng12-dev libfreetype6-dev \
sqlite3 python-pysqlite2 git-core pbzip2 openjdk-6-jre openjdk-6-jdk \
python-crypto  python-dev subversion build-essential python-setuptools \
python-numpy python-scipy"

if ! sudo apt-get install -y ${PKG_LIST}; then
  echo "Could not install packages: $?"
  exit 1
fi
echo -e "Done!\n"

echo "Setting up Database: chromeos_autotest_db in MySQL..."
if mysql -u root -e ';' 2> /dev/null ; then
  PASSWD_STRING=
elif mysql -u root -p"${PASSWD}" -e ';' 2> /dev/null ; then
  PASSWD_STRING="-p${PASSWD}"
else
  PASSWD_STRING="-p"
fi

if ! mysqladmin ping ; then
  sudo service mysql start
fi

CLOBBERDB=
EXISTING_DATABASE=$(mysql -u root "${PASSWD_STRING}" -e "SELECT SCHEMA_NAME \
FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = 'chromeos_autotest_db'")
if [ -n "${EXISTING_DATABASE}" ]; then
  while read -n 1 -p "Clobber existing MySQL database? [y/N]: " CLOBBERDB; do
    echo
    if [[ -z "${CLOBBERDB}" ||
          $(echo ${CLOBBERDB} | egrep -qi 'y|n') -eq 0 ]]; then
      break
    fi
    echo "Please enter y or n."
  done
else
  CLOBBERDB='y'
fi

SQL_COMMAND="drop database if exists chromeos_autotest_db; \
create database chromeos_autotest_db; \
grant all privileges on chromeos_autotest_db.* TO \
'chromeosqa-admin'@'localhost' identified by '${PASSWD}'; \
FLUSH PRIVILEGES;"

if [[ "${CLOBBERDB}" = 'y' || "${CLOBBERDB}" = 'Y' ]]; then
  mysql -u root "${PASSWD_STRING}" -e "${SQL_COMMAND}"
fi
echo -e "Done!\n"

AT_DIR=/usr/local/autotest
echo -n "Bind-mounting your autotest dir at ${AT_DIR}..."
sudo mkdir -p "${AT_DIR}"
sudo mount --bind "${AUTOTEST_DIR}" "${AT_DIR}"
echo -e "Done!\n"

EXISTING_MOUNT=$(egrep "/.+[[:space:]]${AT_DIR}" /etc/fstab || /bin/true)
if [ -n "${EXISTING_MOUNT}" ]; then
  echo "${EXISTING_MOUNT}" | awk '{print $1 " already automounting at " $2}'
  echo "We won't update /etc/fstab, but you should have a line line this:"
  echo -e "${AUTOTEST_DIR}\t${AT_DIR}\tbind defaults,bind\t0\t0"
else
  echo -n "Adding aforementioned bind-mount to /etc/fstab..."
  # Is there a better way to elevate privs and do a redirect?
  sudo su -c \
    "echo -e '${AUTOTEST_DIR}\t${AT_DIR}\tbind defaults,bind\t0\t0' \
    >> /etc/fstab"
  echo -e "Done!\n"
fi

echo -n "Reticulating splines..."
"${AT_DIR}"/utils/build_externals.py &> /dev/null
"${AT_DIR}"/utils/compile_gwt_clients.py -a &> /dev/null
echo -e "Done!\n"

echo "Populating autotest mysql DB..."
"${AT_DIR}"/database/migrate.py sync
"${AT_DIR}"/frontend/manage.py syncdb
# You may have to run this twice.
"${AT_DIR}"/frontend/manage.py syncdb
"${AT_DIR}"/utils/test_importer.py
echo -e "Done!\n"

echo "Configuring apache to run the autotest web interface..."
if [ ! -d /etc/apache2/run ]; then
  sudo mkdir /etc/apache2/run
fi
sudo ln -sf "${AT_DIR}"/apache/apache-conf \
  /etc/apache2/sites-available/autotest-server
# disable currently active default
sudo a2dissite default
# enable autotest server
sudo a2ensite autotest-server
# Enable rewrite module
sudo a2enmod rewrite
# Enable wsgi
sudo a2enmod wsgi
# enable version
sudo a2enmod version
# Setup permissions so that Apache web user can read the proper files.
chmod -R o+r "${AT_DIR}"
find "${AT_DIR}"/ -type d -print0 | xargs --null chmod o+x
chmod o+x "${AT_DIR}"/tko/*.cgi
# restart server
sudo /etc/init.d/apache2 restart

echo "Browse to http://localhost to see if Autotest is working."
echo "For further necessary set up steps, see https://sites.google.com/a/chromium.org/dev/chromium-os/testing/autotest-developer-faq/setup-autotest-server?pli=1"
