import dbus
import dbus.service
import dbus.mainloop.glib
import gobject
import logging
import threading

""" MockFlimflam provides a select few methods from the flimflam
    DBus API so that we can track "dbus-send" invocations sent
    by the shill init scripts.  It could be used as a kernel for
    a test of other facilities that use the shill/flimflam DBus
    API and at that point it should be moved out of this specific
    test. """

class MethodCall(object):
    """ A logged method call to the DBus API. """
    def __init__(self, method, argument):
        self.method = method
        self.argument = argument

class FlimflamManager(dbus.service.Object):
    """ The flimflam DBus Manager object instance.  Methods in this
        object are called whenever a DBus RPC method is invoked. """
    def __init__(self, bus, object_path):
        dbus.service.Object.__init__(self, bus, object_path)
        self.method_calls = []

    @dbus.service.method('org.chromium.flimflam.Manager',
                         in_signature='s', out_signature='o')
    def CreateProfile(self, profile):
        self.add_method_call('CreateProfile', profile)
        return '/'

    @dbus.service.method('org.chromium.flimflam.Manager',
                         in_signature='s', out_signature='')
    def RemoveProfile(self, profile):
        self.add_method_call('RemoveProfile', profile)

    @dbus.service.method('org.chromium.flimflam.Manager',
                         in_signature='s', out_signature='o')
    def PushProfile(self, profile):
        self.add_method_call('PushProfile', profile)
        return '/'

    @dbus.service.method('org.chromium.flimflam.Manager',
                         in_signature='s', out_signature='')
    def PopProfile(self, profile):
        self.add_method_call('PopProfile', profile)

    @dbus.service.method('org.chromium.flimflam.Manager',
                         in_signature='', out_signature='')
    def PopAllUserProfiles(self):
        self.add_method_call('PopAllUserProfiles', '')

    def add_method_call(self, method, arg):
        print "Called method %s" % method
        logging.info("Mock Flimflam method %s called with argument %s" %
                     (method, arg))
        self.method_calls.append(MethodCall(method, arg))

    def get_method_calls(self):
        method_calls = self.method_calls
        self.method_calls = []
        return method_calls

class MockFlimflam(threading.Thread):
    """ This thread object instantiates a mock flimflam manager and
        runs a mainloop that receives DBus API messages. """
    FLIMFLAM = "org.chromium.flimflam"
    def __init__(self):
        threading.Thread.__init__(self)
        gobject.threads_init()

    def run(self):
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SystemBus()
        name = dbus.service.BusName(self.FLIMFLAM, self.bus)
        self.manager = FlimflamManager(self.bus, '/')
        self.mainloop = gobject.MainLoop()
        self.mainloop.run()

    def quit(self):
        self.mainloop.quit()

    def get_method_calls(self):
        return self.manager.get_method_calls()


if __name__ == '__main__':
    MockFlimflam().run()
