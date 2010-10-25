import errno

def get_seconds(utc=True):
    """
    Read the current time out of the RTC
    """
    return int(file('/sys/class/rtc/rtc0/since_epoch').readline())


def write_wake_alarm(alarm_time):
    """
    Write a value to the wake alarm
    """
    f = file('/sys/class/rtc/rtc0/wakealarm', 'w')
    f.write('%s\n' % str(alarm_time))
    f.close()

def set_wake_alarm(alarm_time):
    """
    Set the hardware RTC-based wake alarm to 'alarm_time'.
    """
    try:
        write_wake_alarm(alarm_time)
    except IOError as (errnum, strerror):
        if errnum != errno.EBUSY:
            raise
        write_wake_alarm('clear')
        write_wake_alarm(alarm_time)
        
