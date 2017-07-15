# pylint: disable=missing-docstring
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This is _type for all metadata logged to elasticsearch from here.
STATS_ES_TYPE = 'stats_metadata'


def _prepend_init(_es, _conn, _prefix):
    def wrapper(original):
        """Decorator to override __init__."""

        class _Derived(original):
            def __init__(self, name, connection=None, bare=False,
                         metadata=None):
                name = self._add_prefix(name, _prefix, bare)
                conn = connection if connection else _conn
                super(_Derived, self).__init__(name, conn)
                self.metadata = metadata
                self.es = _es

            def _add_prefix(self, name, prefix, bare=False):
                """
                Since many people run their own local AFE, stats from a local
                setup shouldn't get mixed into stats from prod.  Therefore,
                this function exists to add a prefix, nominally the name of
                the local server, if |name| doesn't already start with the
                server name, so that each person has their own "folder" of
                stats that they can look at.

                However, this functionality might not always be wanted, so we
                allow one to pass in |bare=True| to force us to not prepend
                the local server name. (I'm not sure when one would use this,
                but I don't see why I should disallow it...)

                >>> prefix = 'potato_nyc'
                >>> _add_prefix('rpc.create_job', bare=False)
                'potato_nyc.rpc.create_job'
                >>> _add_prefix('rpc.create_job', bare=True)
                'rpc.create_job'

                @param name The name to append to the server name if it
                            doesn't start with the server name.
                @param bare If True, |name| will be returned un-altered.
                @return A string to use as the stat name.

                """
                if not bare and not name.startswith(prefix):
                    name = '%s.%s' % (prefix, name)
                return name

        return _Derived
    return wrapper
