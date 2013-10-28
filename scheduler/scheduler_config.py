import common
from autotest_lib.client.common_lib import global_config

CONFIG_SECTION = 'SCHEDULER'

class SchedulerConfig(object):
    """
    Contains configuration that can be changed during scheduler execution.
    """
    FIELDS = {'max_processes_per_drone': 'max_processes_per_drone',
              'max_processes_warning_threshold':
                  'max_processes_warning_threshold',
              'max_processes_started_per_cycle': 'max_jobs_started_per_cycle',
              'clean_interval': 'clean_interval_minutes',
              'max_parse_processes': 'max_parse_processes',
              'tick_pause_sec': 'tick_pause_sec',
              'max_transfer_processes': 'max_transfer_processes',
              'secs_to_wait_for_atomic_group_hosts':
                  'secs_to_wait_for_atomic_group_hosts',
              'reverify_period_minutes': 'reverify_period_minutes',
              'reverify_max_hosts_at_once': 'reverify_max_hosts_at_once',
              'max_repair_limit': 'max_repair_limit',
              'max_provision_retries': 'max_provision_retries',
             }


    def __init__(self):
        self.read_config()


    def read_config(self):
        config = global_config.global_config
        config.parse_config_file()
        for field, config_option in self.FIELDS.iteritems():
            if field == 'max_processes_warning_threshold':
                data_type = float
            else:
                data_type = int
            setattr(self, field, config.get_config_value(CONFIG_SECTION,
                                                         config_option,
                                                         type=data_type))


config = SchedulerConfig()
