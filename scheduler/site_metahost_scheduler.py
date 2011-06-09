import random
from autotest_lib.client.common_lib import utils
from autotest_lib.scheduler import metahost_scheduler
from autotest_lib.scheduler import scheduler_models
from autotest_lib.server.hosts import abstract_ssh


class SSHRandomLabelMetahostScheduler(metahost_scheduler.MetahostScheduler):
    """Label metahost scheduler with host randomization and SSH check."""
    def can_schedule_metahost(self, queue_entry):
        return bool(queue_entry.meta_host)


    def schedule_metahost(self, queue_entry, scheduling_utility):
        label_id = queue_entry.meta_host

        # Take the list of all hosts in the label and subtract the ineligible.
        hosts_in_label = (
            scheduling_utility.hosts_in_label(label_id)
            - scheduling_utility.ineligible_hosts_for_entry(queue_entry))

        # Create a random sampling of hosts, ensuring test coverage is uniform.
        for host_id in random.sample(hosts_in_label, len(hosts_in_label)):
            if not scheduling_utility.is_host_usable(host_id):
                scheduling_utility.remove_host_from_label(host_id, label_id)
                continue
            if not scheduling_utility.is_host_eligible_for_job(
                    host_id, queue_entry):
                continue

            # Perform an SSH check to ensure the host is available. Doing this
            # here instead of allowing the queue entry to be rescheduled after
            # verify fails saves a significant amount of time.
            host_data = scheduler_models.Host(id=host_id)
            try:
                utils.run('%s %s "true"' % (
                    abstract_ssh.make_ssh_command(), host_data.hostname),
                          timeout=5)
            except:
                scheduling_utility.remove_host_from_label(host_id, label_id)
                continue

            # Remove the host from our cached internal state before returning.
            scheduling_utility.remove_host_from_label(host_id, label_id)
            host = scheduling_utility.pop_host(host_id)
            queue_entry.set_host(host)
            return


def get_metahost_schedulers():
    return [SSHRandomLabelMetahostScheduler()]
