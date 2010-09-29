def get_seconds(utc=True):
    """
    Read the current time out of the RTC
    """
    return int(file('/sys/class/rtc/rtc0/since_epoch').readline())


def set_wake_alarm(alarm_time):
    """
    Set the hardware RTC-based wake alarm to 'alarm_time'.
    """
    file('/sys/class/rtc/rtc0/wakealarm', 'w').write("%s\n" % str(alarm_time))


