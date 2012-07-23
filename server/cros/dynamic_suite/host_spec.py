# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from itertools import chain


def order_by_complexity(host_spec_list):
    """
    Returns a new list of HostSpecs, ordered from most to least complex.

    Currently, 'complex' means that the spec contains more labels.
    We may want to get smarter about this.

    @param host_spec_list: a list of HostSpec objects.
    @return a new list of HostSpec, ordered from most to least complex.
    """
    def extract_label_list_len(host_spec):
        return len(host_spec.labels)
    return sorted(host_spec_list, key=extract_label_list_len, reverse=True)


def is_trivial(host_spec_list):
    """
    Returns true if this is a 'trivial' list of HostSpec objects.

    A 'trivial' list of HostSpec objects is defined as a list of one HostSpec.

    @param host_spec_list: a list of HostSpec objects.
    @return True if this is a list of size 1, False otherwise.
    """
    return len(host_spec_list) == 1


def trivial_get_spec_and_hosts(host_specs, hosts_per_spec):
    """Given a trivial list of HostSpec, extract hosts from hosts_per_spec.

    Given a trivial list of HostSpec objects, pull out the spec and use it to
    get the associated hosts out of hosts_per_spec.  Return the spec and the
    host list as a pair.

    @param host_specs: an iterable of HostSpec objects.
    @param hosts_per_spec: map of {HostSpec: [list, of, hosts]}
    @return (HostSpec, [list, of, hosts]}
    """
    spec = host_specs.pop()
    return spec, hosts_per_spec[spec]


class HostGroup(object):
    """A high-level specification of a group of hosts.

    A HostGroup represents a group of hosts against which a job can be
    scheduled.  An instance is capable of returning arguments that can specify
    this group in a call to AFE.create_job().
    """
    def __init__(self):
        pass


    def as_args(self):
        """Return args suitable for passing to AFE.create_job()."""
        raise NotImplementedError()


    def size(self):
        """Returns the number of hosts specified by the group."""
        raise NotImplementedError()


    def mark_host_success(self, hostname):
        """Marks the provided host as successfully reimaged.

        @param hostname: the name of the host that was reimaged.
        """
        raise NotImplementedError()


    def enough_hosts_succeeded(self):
        """Returns True if enough hosts in the group were reimaged for use."""
        raise NotImplementedError()


    @property
    def unsatisfied_specs(self):
        return []


    @property
    def doomed_specs(self):
        return []


class ExplicitHostGroup(HostGroup):
    """A group of hosts, specified by name, to be reimaged for use.

    @var _hostname_data_dict: {hostname: HostData()}.
    """

    class HostData(object):
        """A HostSpec of a given host, and whether it reimaged successfully."""
        def __init__(self, spec):
            self.spec = spec
            self.image_success = False


    def __init__(self, hosts_per_spec={}):
        """Constructor.

        @param hosts_per_spec: {HostSpec: [list, of, hosts]}.
                               Each host can appear only once.
        """
        self._hostname_data_dict = {}
        self._unsatisfied_specs = []
        for spec, host_list in hosts_per_spec.iteritems():
            for host in host_list:
                self.add_host_for_spec(spec, host)


    def _host_datas(self):
        return self._hostname_data_dict.itervalues()


    def as_args(self):
        return {'hosts': self._hostname_data_dict.keys()}


    def size(self):
        return len(self._hostname_data_dict)


    def mark_host_success(self, hostname):
        self._hostname_data_dict[hostname].image_success = True


    def enough_hosts_succeeded(self):
        """If _any_ hosts were reimaged, that's enough."""
        return True in [d.image_success for d in self._host_datas()]


    def add_host_for_spec(self, spec, host):
        """Add a new host for the given HostSpec to the group.

        @param spec: HostSpec to associate host with.
        @param host: a Host object; each host can appear only once.
        """
        if not host:
            if spec not in [d.spec for d in self._host_datas()]:
                self._unsatisfied_specs.append(spec)
            return

        if self.contains_host(host):
            raise ValueError('A Host can appear in an '
                             'ExplicitHostGroup only once.')
        if spec in self._unsatisfied_specs:
            self._unsatisfied_specs.remove(spec)
        self._hostname_data_dict[host.hostname] = self.HostData(spec)


    def contains_host(self, host):
        """Whether host is already part of this HostGroup

        @param host: a Host object.
        @return True if the host is already tracked; False otherwise.
        """
        return host.hostname in self._hostname_data_dict


    @property
    def unsatisfied_specs(self):
        return self._unsatisfied_specs


    @property
    def doomed_specs(self):
        specs = set([d.spec for d in self._host_datas()])
        for data in self._hostname_data_dict.itervalues():
            if data.image_success:
                specs.remove(data.spec)
        return specs


class MetaHostGroup(HostGroup):
    """A group of hosts, specified by a meta_host and deps, to be reimaged.

    @var _meta_hosts: a meta_host, as expected by AFE.create_job()
    @var _dependencies: list of dependencies that all hosts to be used
                        must satisfy
    @var _successful_hosts: set of successful hosts.
    """
    def __init__(self, labels, num):
        """Constructor.

        Given a set of labels specifying what kind of hosts we need,
        and the num of hosts we need, build a meta_host and dependency list
        that represent this group of hosts.

        @param labels: list of labels indicating what kind of hosts need
                       to be reimaged.
        @param num: how many hosts we'd like to reimage.
        """
        self._spec = HostSpec(labels)
        self._meta_hosts = labels[:1]*num
        self._dependencies = labels[1:]
        self._successful_hosts = set()


    def as_args(self):
        return {'meta_hosts': self._meta_hosts,
                'dependencies': self._dependencies}


    def size(self):
        return len(self._meta_hosts)


    def mark_host_success(self, hostname):
        self._successful_hosts.add(hostname)


    def enough_hosts_succeeded(self):
        return self._successful_hosts


    @property
    def doomed_specs(self):
        if self._successful_hosts:
            return []
        return [self._spec]


class HostSpec(object):
    """Specifies a kind of host on which dependency-having tests can be run.

    Wraps a list of labels, for the purposes of specifying a set of hosts
    on which a test with matching dependencies can be run.
    """

    def __init__(self, labels):
        self._labels = sorted(labels)
        # To amortize cost of __hash__()
        self._str = 'HostSpec %r' % self._labels


    @property
    def labels(self):
        return self._labels


    def __str__(self):
        return self._str


    def __repr__(self):
        return self._str


    def __lt__(self, other):
        return str(self) < str(other)


    def __le__(self, other):
        return str(self) <= str(other)


    def __eq__(self, other):
        return str(self) == str(other)


    def __ne__(self, other):
        return str(self) != str(other)


    def __gt__(self, other):
        return str(self) > str(other)


    def __ge__(self, other):
        return str(self) >= str(other)


    def __hash__(self):
        """Allows instances to be correctly deduped when used in a set."""
        return hash(str(self))
