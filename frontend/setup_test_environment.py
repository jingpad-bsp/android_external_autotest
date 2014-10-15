import tempfile, shutil, os
from django.core import management
from django.conf import settings
import common

# we need to set DATABASE_ENGINE now, at import time, before the Django database
# system gets initialized.
# django.conf.settings.LazySettings is buggy and requires us to get something
# from it before we set stuff on it.
getattr(settings, 'DATABASES')
settings.DATABASES['default']['ENGINE'] = (
    'autotest_lib.frontend.db.backends.afe_sqlite')
settings.DATABASES['default']['NAME'] = ':memory:'

settings.DATABASES['readonly'] = {}
settings.DATABASES['readonly']['ENGINE'] = (
    'autotest_lib.frontend.db.backends.afe_sqlite')
settings.DATABASES['readonly']['NAME'] = ':memory:'

from django.db import connections
from autotest_lib.frontend.afe import readonly_connection

connection = connections['default']
connection_readonly = connections['readonly']

def run_syncdb(verbosity=0):
    management.call_command('syncdb', verbosity=verbosity, interactive=False)
    management.call_command('syncdb', verbosity=verbosity, interactive=False,
                             database='readonly')

def destroy_test_database():
    connection.close()
    connection_readonly.close()
    # Django brilliantly ignores close() requests on in-memory DBs to keep us
    # naive users from accidentally destroying data.  So reach in and close
    # the real connection ourselves.
    # Note this depends on Django internals and will likely need to be changed
    # when we upgrade Django.
    for con in [connection, connection_readonly]:
        real_connection = con.connection
        if real_connection is not None:
            real_connection.close()
            con.connection = None


def set_up():
    run_syncdb()
    readonly_connection.set_globally_disabled(True)


def tear_down():
    readonly_connection.set_globally_disabled(False)
    destroy_test_database()


def print_queries():
    """
    Print all SQL queries executed so far.  Useful for debugging failing tests -
    you can call it from tearDown(), and then execute the single test case of
    interest from the command line.
    """
    for query in connection.queries:
        print query['sql'] + ';\n'
