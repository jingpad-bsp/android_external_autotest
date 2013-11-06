"""
Rdb server module.
"""
import logging
from autotest_lib.site_utils.graphite import stats


_timer = stats.Timer('rdb')

def _check_acls(job_acls, host_acls):
    if job_acls is None or host_acls is None:
        return False
    return len(host_acls.intersection(job_acls))


def _check_deps(job_deps, host_labels):
    if job_deps is None or host_labels is None:
        return False
    return len(job_deps - host_labels) == 0


def validate_host_assignment(job_info, host_info):
    """ Validate this job<->host pairing.

    @param job_info: Information about the job as determined by
                     the client rdb module.
    @param host_info: Information about the host as determined by
                      get_host_info.

    @return: True if the job<->host pairing is valid, False otherwise.
             False, if we don't have enough information to make a decision.
    """
    one_time_host = host_info.get('invalid') and job_info.get('host_id')

    return (_check_acls(job_info.get('acls'), host_info.get('acls')) and
            _check_deps(job_info.get('deps'), host_info.get('labels')) and
            not host_info.get('invalid', True) or one_time_host and
            not host_info.get('locked', True))


def get_host_info(host_scheduler, host_id):
    """
    Utility method to parse information about a host into a dictionary.

    Ideally this can just return the Host object, but doing this has the
    following advantages:
        1. Changes to the schema will only require changes to this method.
        2. We can reimplement this method to make use of django caching.
        3. We can lock rows of the host table in a centralized location.

    @param host_id: id of the host to get information about.
    @return: A dictionary containing all information needed to make a
             scheduling decision regarding this host.
    """
    acls = host_scheduler._host_acls.get(host_id, set())
    labels = host_scheduler._host_labels.get(host_id, set())
    host_info = {'labels': labels, 'acls': acls}
    host = host_scheduler._hosts_available.get(host_id)
    if host:
        host_info.update({'locked': host.locked, 'invalid': host.invalid})
    return host_info


def _order_labels(host_scheduler, labels):
    """Given a list of labels, order them by available host count.

    To make a scheduling decision, we need a host that matches all dependencies
    of a job, hence the most restrictive search space we can use is the list
    of ready hosts that have the least frequent label.

    @param labels: A list of labels. If no hosts are available in a label,
                   it will be the first in this list.
    """
    label_count = [len(host_scheduler._label_hosts.get(label, []))
                   for label in labels]
    return [label_tuple[1] for label_tuple in sorted(zip(label_count, labels))]


@_timer.decorate
def get_host(host_scheduler, job_info):
    """
    Get a host matching the job's selection criterion.

    - Get all hosts in rarest label.
    - Check which ones are still usable.
    - Return the first of these hosts that passes our validity checks.

    @param job_info: A dictionary of job information needed to pick a host.

    @return: A host object from the available_hosts map.
    """

    # A job must at least have one dependency (eg:'board:') in order for us to
    # find a host for it. To do so we use 2 data structures of host_scheduler:
    # - label to hosts map: to count label frequencies, and get hosts in a label
    # - hosts_available map: to mark a host as used, as it would be difficult
    #   to delete this host from all the label keys it has, in the label to
    #   hosts map.
    rarest_label = _order_labels(host_scheduler, job_info.get('deps'))[0]

    # TODO(beeps): Once we have implemented locking in afe_hosts make this:
    # afe.models.Host.object.filter(locked).filter(acls).filter(labels)...
    # where labels are chained according to frequency. Currently this will
    # require a join across all hqes which could be expensive, and is
    # unnecessary anyway since we need to move away from this scheduling model.
    hosts_considered = host_scheduler._label_hosts.get(rarest_label, [])
    for host_id in hosts_considered:
        host = host_scheduler._hosts_available.get(host_id)
        host_info = get_host_info(host_scheduler, host_id)
        if host and validate_host_assignment(job_info, host_info):
            return host
