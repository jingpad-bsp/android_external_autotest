from autotest_lib.client.common_lib.cros import get_usb_devices
from autotest_lib.client.common_lib.cros.cfm import cfm_usb_devices


class UsbDataCollector(object):
    """Utility class for collecting USB data from the DUT."""

    def __init__(self, host):
        """
        Constructor
        @param host the device under test (CrOS).
        """
        self._host = host

    def collect(self):
        """Collecting usb device data."""
        usb_devices = (self._host.run('usb-devices', ignore_status=True).
                       stdout.strip().split('\n\n'))
        return get_usb_devices._extract_usb_data(
            '\nUSB-Device\n'+'\nUSB-Device\n'.join(usb_devices))


class UsbDevices(object):
    """Utility class for obtaining info about connected USB devices."""

    def __init__(self, usb_data_collector):
        """
        Constructor
        @param usb_data_collector used for collecting USB data
        from the device.
        """
        self._usb_data_collector = usb_data_collector

    def __collect_usb_data(self):
        """Private method for collecting usb device data."""
        return self._usb_data_collector.collect()

    # TODO(malmnas): it probably makes more sense to let the key be
    # an instance of cfm/UsbDevice instead of vid_pid.
    def get_camera_counts(self):
        """
        Returns the number of cameras for each type.
        @returns a dictionary where the key is VID_PID and value
        is the number of cameras of that type.
        """
        return get_usb_devices._get_cameras(self.__collect_usb_data())


    def get_speaker_counts(self):
        """
        Get the number of speakers of each type.
        @returns a list of (UsbDevice, int) tuples.
        """
        usbdata = self.__collect_usb_data()
        number_speakers = []
        for speaker in cfm_usb_devices.get_speakers():
            count = len(get_usb_devices._filter_by_vid_pid(
                usbdata, speaker.vid_pid))
            number_speakers.append((speaker, count))
        return number_speakers


    def get_dual_speakers(self):
        """
        @returns the UsbDevice constant representing the dual speakers that are
        connected. If no dual speakers are found, None is returned.
        """
        for speaker, count in self.get_speaker_counts():
            if count == 2:
                return speaker
        return None

    # TODO(malmnas): method should probably take a cfm/UsbDevice as
    # parameter instead of vid_pid.
    def verify_usb_device_interfaces_ok(self, vid_pid):
        """
        Verify usb device interfaces.

        If the interface check fails, a RuntimeError is raised.

        @param vid_pid the VID_PID of devices to be checked.
        @return None
        """
        return get_usb_devices._verify_usb_device_ok(
            self.__collect_usb_data(), vid_pid)
