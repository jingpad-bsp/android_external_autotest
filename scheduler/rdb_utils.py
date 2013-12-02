"""RDB utilities.

Do not import rdb or autotest modules here to avoid cyclic dependencies.
"""
import itertools
import collections


class RDBException(Exception):
    """Generic RDB exception."""

    def wire_format(self):
        """Convert the exception to a format better suited to an rpc response.
        """
        return str(self)


class RDBRequestMeta(type):
    """Metaclass for constructing rdb requests.

    This meta class creates a read-only request template by combining the
    request_arguments of all classes in the inheritence hierarchy into a namedtuple.
    """
    def __new__(cls, name, bases, dctn):
        for base in bases:
            try:
                dctn['_request_args'].update(base._request_args)
            except AttributeError:
                pass
        dctn['template'] = collections.namedtuple('template',
                                                  dctn['_request_args'])
        return type.__new__(cls, name, bases, dctn)


# RDB Request classes: Used in conjunction with the request managers defined in
# rdb_lib. Each class defines the set of fields the rdb needs to fulfill the
# request, and a hashable request object the request managers use to identify
# a response with a request.
class RDBRequest(object):
    """Base class for an rdb request.

    All classes inheriting from RDBRequest will need to specify a list of
    request_args necessary to create the request, and will in turn get a
    request that the rdb understands.
    """
    __metaclass__ = RDBRequestMeta
    __slots__ = set(['_request_args', '_request'])
    _request_args = set([])


    def __init__(self, **kwargs):
        for key,value in kwargs.iteritems():
            try:
                hash(value)
            except TypeError as e:
                raise RDBException('All fields of a %s must be hashable. '
                                   '%s: %s, %s failed this test.' %
                                   (self.__class__, key, type(value), value))
        try:
            self._request = self.template(**kwargs)
        except TypeError:
            raise RDBException('Creating %s requires args %s, got %s ' %
                    (self.__class__, self.template._fields, kwargs.keys()))


    def get_request(self):
        """Returns a request that the rdb understands.

        @return: A named tuple with all the fields necessary to make a request.
        """
        return self._request


class HashableDict(dict):
    """A hashable dictionary.

    This class assumes all values of the input dict are hashable.
    """

    def __hash__(self):
        return hash(tuple(sorted(self.items())))


class HostRequest(RDBRequest):
    """Basic request for information about a single host.

    Eg: HostRequest(host_id=x): Will return all information about host x.
    """
    _request_args =  set(['host_id'])


class UpdateHostRequest(HostRequest):
    """Defines requests to update hosts.

    Eg:
        UpdateHostRequest(host_id=x, payload={'afe_hosts_col_name': value}):
            Will update column afe_hosts_col_name with the given value, for
            the given host_id.

    @raises RDBException: If the input arguments don't contain the expected
        fields to make the request, or are of the wrong type.
    """
    _request_args = set(['payload'])


    def __init__(self, **kwargs):
        try:
            kwargs['payload'] = HashableDict(kwargs['payload'])
        except (KeyError, TypeError) as e:
            raise RDBException('Creating %s requires args %s, got %s ' %
                    (self.__class__, self.template._fields, kwargs.keys()))
        super(UpdateHostRequest, self).__init__(**kwargs)


class AcquireHostRequest(HostRequest):
    """Defines requests to acquire hosts.

    Eg:
        AcquireHostRequest(host_id=None, deps=[d1, d2], acls=[a1, a2]): Will
            acquire and return a host that matches the specified deps/acls.
        AcquireHostRequest(host_id=x, deps=[d1, d2], acls=[a1, a2]) : Will
            acquire and return host x, after checking deps/acls match.

    @raises RDBException: If the the input arguments don't contain the expected
        fields to make a request, or are of the wrong type.
    """
    _request_args = set(['deps', 'acls'])


    def __init__(self, **kwargs):
        try:
            kwargs['deps'] = frozenset(kwargs['deps'])
            kwargs['acls'] = frozenset(kwargs['acls'])
        except (KeyError, TypeError) as e:
            raise RDBException('Creating %s requires args %s, got %s ' %
                    (self.__class__, self.template._fields, kwargs.keys()))
        super(AcquireHostRequest, self).__init__(**kwargs)


# Custom iterators: Used by the rdb to lazily convert the iteration of a
# queryset to a database query and return an appropriately formatted response.
class RememberingIterator(object):
    """An iterator capable of reproducing all values in the input generator.
    """

    #pylint: disable-msg=C0111
    def __init__(self, gen):
        self.current, self.history = itertools.tee(gen)
        self.items = []


    def __iter__(self):
        return self


    def next(self):
        return self.current.next()


    def get_all_items(self):
        """Get all the items in the generator this object was created with.

        @return: A list of items.
        """
        if not self.items:
            self.items = list(self.history)
        return self.items


class LabelIterator(RememberingIterator):
    """A RememberingIterator for labels.

    Within the rdb any label/dependency comparisons are performed based on label
    ids. However, the host object returned needs to contain label names instead.
    This class returns the label id when iterated over, but a list of all label
    names when accessed through get_all_items.
    """


    def next(self):
        return super(LabelIterator, self).next().id


    def get_all_items(self):
        """Get all label names of the labels in the input generator.

        @return: A list of label names.
        """
        return [label.name
                for label in super(LabelIterator, self).get_all_items()]


# Rdb host adapters: Help in making a raw database host object more ameanable
# to the classes and functions in the rdb and/or rdb clients.
class RDBServerHostWrapper(object):
    """A host wrapper for the raw database object.
    """


    def __init__(self, host):
        self.id = host.id
        self.hostname = host.hostname
        self.status = host.status
        self.protection = host.protection
        self.dirty = host.dirty
        self.invalid = host.invalid
        self.labels = LabelIterator(
                (label for label in host.labels.all()))
        self.acls = RememberingIterator(
                (acl.id for acl in host.aclgroup_set.all()))
        platform = host.platform()
        self.platform = platform.name if platform else None


    def wire_format(self):
        """Returns all information needed to scheduler jobs on the host.

        @return: A dictionary of host information.
        """
        host_info = {}
        for key, value in self.__dict__.iteritems():
            if isinstance(value, RememberingIterator):
                host_info[key] = value.get_all_items()
            else:
                host_info[key] = value
        return host_info


def return_rdb_host(func):
    """Decorator for functions that return a list of Host objects.

    @param func: The decorated function.
    @return: A functions capable of converting each host_object to a
        RDBServerHostWrapper.
    """
    def get_rdb_host(*args, **kwargs):
        """Takes a list of hosts and returns a list of host_infos.

        @param hosts: A list of hosts. Each host is assumed to contain
            all the fields in a host_info defined above.
        @return: A list of RDBServerHostWrappers, one per host, or an empty
            list is no hosts were found..
        """
        hosts = func(*args, **kwargs)
        return [RDBServerHostWrapper(host) for host in hosts]
    return get_rdb_host
