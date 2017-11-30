"""Utility class representing a CfM USB device.

This class represents actual data found by running the usb-device command.
"""

class UsbDevice(object):
  """Utility class representing a CfM USB device."""

  def __init__(self, vid, pid, product, interfaces, bus, port):
      """
      Constructor.

      @param vid: Vendor ID. String.
      @param pid: Product ID. String.
      @param product: Product description. String
      @param interfaces: List of strings.
      @param bus: The bus this device is connected to. Number.
      @param port: The port number as specified in /sys/bus/usb/devices/usb*.
          Number.
      """
      self._vid = vid
      self._pid = pid
      self._product = product
      self._interfaces = interfaces
      self._bus = bus
      self._port = port

  @property
  def vendor_id(self):
      """Returns the vendor id for this USB device."""
      return self._vid

  @property
  def product_id(self):
      """Returns the product id for this USB device."""
      return self._pid

  @property
  def vid_pid(self):
      """Return the <vendor_id>:<product_id> as a string."""
      return '%s:%s' % (self._vid, self._pid)

  @property
  def product(self):
      """Returns the product name."""
      return self._product

  @property
  def interfaces(self):
      """Returns the list of interfaces."""
      return self._interfaces

  @property
  def port(self):
      """Returns the port this USB device is connected to."""
      return self._port

  @property
  def bus(self):
      """Returns the bus this USB device is connected to."""
      return self._bus

  def interfaces_match_spec(self, usb_device_spec):
      """
      Checks that the interfaces of this device matches those of the given spec.

      @param usb_device_spec an instance of UsbDeviceSpec
      @return True or False
      """
      # List of expected interfaces. This might be a sublist of the actual
      # list of interfaces. Note: we have to use lists and not sets since
      # the list of interfaces might contain duplicates.
      expected_interfaces = sorted(usb_device_spec.interfaces)
      length = len(expected_interfaces)
      actual_interfaces = sorted(self.interfaces)
      return actual_interfaces[0:length] == expected_interfaces


  def __str__(self):
      return "%s (%s)" % (self._product, self.vid_pid)
