"""Utility class representing a CfM USB device.

The set of known USB devices are listed in cfm_usb_devices.py
"""

class UsbDevice(object):
  """Utility class representing a CfM USB device."""

  # Dictionary of all UsbDevice instance that have been created.
  # Mapping from vid_pid to UsbDevice instance.
  _all_devices = {}

  def __init__(self, vid, pid, name, interfaces):
      """
      Constructor.

      @param vid: Vendor ID. String.
      @param pid: Product ID. String.
      @param name: Human readable name. String.
      @param interfaces: List of strings
      """
      self._vid = vid
      self._pid = pid
      self._name = name
      self._interfaces = interfaces
      self.__class__._all_devices[self.vid_pid] = self

  @classmethod
  def get_usb_device(cls, vid_pid):
      """Looks up UsbDevice by vid_pid."""
      return cls._all_devices.get(vid_pid)

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
  def name(self):
      """Returns the human friendly name for this USB device."""
      return self._name

  @property
  def full_name(self):
      """Returns the name of this device plus the vidpid."""
      return "%s (%s)" % (self._name, self.vid_pid)

  @property
  def interfaces(self):
      """Returns the list of interfaces."""
      return self._interfaces
