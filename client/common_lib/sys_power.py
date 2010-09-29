import os


def set_state(state):
    """
    Set the system power state to 'state'.
    """
    file('/sys/power/state', 'w').write("%s\n" % state)


def suspend_to_ram():
    """
    Suspend the system to RAM (S3)
    """
    if os.path.exists('/usr/bin/powerd_suspend'):
        os.system('/usr/bin/powerd_suspend')
    else:
        set_power_state('mem')


def suspend_to_disk():
    """
    Suspend the system to disk (S4)
    """
    set_power_state('disk')

def standby():
    """
    Power-on suspend (S1)
    """
    set_power_state('standby')

