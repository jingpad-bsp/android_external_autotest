from autotest_lib.client.common_lib.cros import get_usb_devices
from autotest_lib.client.common_lib.cros.cfm import cfm_usb_devices
from autotest_lib.client.common_lib.cros.cfm import usb_device


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

    def _create_usb_device(self, usbdata):
        return usb_device.UsbDevice(
            vid=usbdata['Vendor'],
            pid=usbdata['ProdID'],
            product=usbdata.get('Product', 'Not available'),
            interfaces=usbdata['intdriver'])

    def get_usb_devices(self):
        """
        Returns the list of UsbDevices connected to the DUT.
        @returns A list of UsbDevice instances.
        """
        usbdata = self._usb_data_collector.collect()
        return [self._create_usb_device(d) for d in usbdata]

    def get_devices_by_spec(self, spec):
        """
        Returns all UsbDevices that match the given spec.
        @param spec instance of UsbDeviceSpec
        @returns a list UsbDevice instances.
        """
        return [d for d in self.get_usb_devices()
                if d.vid_pid == spec.vid_pid]

    def verify_usb_device_interfaces_ok(self, usb_device):
        """
        Verify usb device interfaces.

        If the interface check fails, a RuntimeError is raised.

        @param usb_device Instance of UsbDevice.
        @return None
        """
        device_found = False
        # Retrieve the device spec for this vid:pid
        usb_device_spec = cfm_usb_devices.get_usb_device_spec(
            usb_device.vid_pid)
        if not usb_device_spec:
            raise RuntimeError('Unknown usb device: %s.', usb_device)
        # List of expected interfaces. This might be a sublist of the actual
        # list of interfaces. Note: we have to use lists and not sets since
        # the list of interfaces might contain duplicates.
        expected_interfaces = sorted(usb_device_spec.interfaces)
        length = len(expected_interfaces)
        actual_interfaces = sorted(usb_device.interfaces)
        if not actual_interfaces[0:length] == expected_interfaces:
            raise RuntimeError(
                'Device %s has unexpected interfaces.'
                'Expected: %s. Actual: %s' % (
                    usb_device, expected_interfaces, actual_interfaces))
