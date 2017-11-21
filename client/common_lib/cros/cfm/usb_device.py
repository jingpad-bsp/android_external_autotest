"""Utility class representing a CfM USB device.

This class represents actual data found by running the usb-device command.
"""

class UsbDevice(object):
  """Utility class representing a CfM USB device."""

  def __init__(self, vid, pid, product, interfaces):
      """
      Constructor.

      @param vid: Vendor ID. String.
      @param pid: Product ID. String.
      @param product: Product description. String
      @param interfaces: List of strings
      """
      self._vid = vid
      self._pid = pid
      self._product = product
      self._interfaces = interfaces

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

  def __str__(self):
      return "%s (%s)" % (self._product, self.vid_pid)
