#pylint: disable-msg=C0111

# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Django database Router

Django gets configured with two databases in frontend/settings.py.
- The default database
    - This database should be used for most things.
    - For the master, this is the global database.
    - For shards, this this is the shard-local database.
- The global database
    - For the master, this is the same database as default, which is the global
      database.
    - For the shards, this is the global database (the same as for the master).

The reason shards need two distinct databases for different objects is, that
the tko parser should always write to the global database. Otherwise test
results wouldn't be synced back to the master and would not be accessible in one
place.

Therefore this class will route all queries that involve `tko_`-prefixed tables
to the global database. For all others this router will not give a hint, which
means the default database will be used.
"""

class Router(object):
    """
    Decide if an object should be written to the default or to the global db.

    This is an implementaton of Django's multi-database router interface:
    https://docs.djangoproject.com/en/1.5/topics/db/multi-db/
    """

    def _should_be_in_global(self, model):
        """Returns True if the model should be stored in the global db"""
        return model._meta.db_table.startswith('tko_')


    def db_for_read(self, model, **hints):
        """
        Decides if the global database should be used for a reading access.

        @param model: Model to decide for.

        @returns: 'global' for all tko models, None otherwise. None means the
                  router doesn't have an opinion.
        """
        if self._should_be_in_global(model):
            return 'global'
        return None


    def db_for_write(self, model, **hints):
        """
        Decides if the global database should be used for a writing access.

        @param model: Model to decide for.

        @returns: 'global' for all tko models, None otherwise. None means the
                  router doesn't have an opinion.
        """
        if self._should_be_in_global(model):
            return 'global'
        return None


    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations only if either both are in tko_ tables or none is.

        @param obj1: First object involved in the relation.
        @param obj2: Second object involved in the relation.

        @returns False, if the relation should be prohibited,
                 None, if the router doesn't have an opinion.
        """
        if not self._should_be_in_global(
                type(obj1)) == self._should_be_in_global(type(obj2)):
            return False
        return None
