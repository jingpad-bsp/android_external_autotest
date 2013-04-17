import os

import common

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'autotest_lib.frontend.settings')

def enable_autocommit():
    from django.db import connection
    connection.cursor() # ensure a connection is open
    connection.connection.autocommit(True)
