# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# Django settings for frontend project.

import os
import common
from autotest_lib.client.common_lib import global_config

DEBUG = True
TEMPLATE_DEBUG = DEBUG

FULL_ADMIN = False

ADMINS = (
    # ('Your Name', 'your_email@domain.com'),
)

MANAGERS = ADMINS

DATABASE_ENGINE = 'mysql'      # 'postgresql_psycopg2', 'postgresql',
                               # 'mysql', 'sqlite3' or 'ado_mssql'.
DATABASE_PORT = ''             # Set to empty string for default.
                               # Not used with sqlite3.

c = global_config.global_config
_section = 'AUTOTEST_WEB'
DATABASE_HOST = c.get_config_value(_section, "host")
# Or path to database file if using sqlite3.
DATABASE_NAME = c.get_config_value(_section, "database")
# The following not used with sqlite3.
DATABASE_USER = c.get_config_value(_section, "user")
DATABASE_PASSWORD = c.get_config_value(_section, "password", default='')

DATABASE_READONLY_HOST = c.get_config_value(_section, "readonly_host",
                                            default=DATABASE_HOST)
DATABASE_READONLY_USER = c.get_config_value(_section, "readonly_user",
                                            default=DATABASE_USER)
if DATABASE_READONLY_USER != DATABASE_USER:
    DATABASE_READONLY_PASSWORD = c.get_config_value(_section,
                                                    "readonly_password",
                                                    default='')
else:
    DATABASE_READONLY_PASSWORD = DATABASE_PASSWORD


# Local time zone for this installation. Choices can be found here:
# http://www.postgresql.org/docs/8.1/static/datetime-keywords.html#DATETIME-TIMEZONE-SET-TABLE
# although not all variations may be possible on all operating systems.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'America/Los_Angeles'

# Language code for this installation. All choices can be found here:
# http://www.w3.org/TR/REC-html40/struct/dirlang.html#langcodes
# http://blogs.law.harvard.edu/tech/stories/storyReader$15
LANGUAGE_CODE = 'en-us'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.load_template_source',
    'django.template.loaders.app_directories.load_template_source',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'frontend.apache_auth.ApacheAuthMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.doc.XViewMiddleware',
    'frontend.shared.json_html_formatter.JsonToHtmlMiddleware',
)

ROOT_URLCONF = 'dashboard.urls'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    os.path.abspath(os.path.dirname(__file__) + '/templates')
)

INSTALLED_APPS = (
    'dashboard',
)

AUTHENTICATION_BACKENDS = (
    'frontend.apache_auth.SimpleAuthBackend',
)
