import dbus, dbus.mainloop.glib, gobject, sys, time

ssid         = sys.argv[1]
wait_timeout = sys.argv[2]

bus_loop = dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus(mainloop=bus_loop)
manager = dbus.Interface(bus.get_object("org.moblin.connman", "/"),
    "org.moblin.connman.Manager")

mprops = manager.GetProperties()
for path in mprops["Services"]:
    service = dbus.Interface(bus.get_object("org.moblin.connman", path),
        "org.moblin.connman.Service")
    sprops = service.GetProperties()
    if sprops.get("Name", None) != ssid:
        continue
    wait_time = 0
    try:
        service.Disconnect()
        while wait_time < wait_timeout:
            sprops = service.GetProperties()
            state = sprops.get("State", None)
#           print>>sys.stderr, "time %3.1f state %s" % (wait_time, state)
            if state == "idle":
                break
            time.sleep(.5)
            wait_time += .5
    except:
        pass
    print "disconnect in %3.1f secs" % wait_time
    break
sys.exit(0)

