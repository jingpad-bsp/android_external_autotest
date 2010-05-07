import dbus, dbus.mainloop.glib, gobject, logging, re, sys, time

ssid           = sys.argv[1]
security       = sys.argv[2]
psk            = sys.argv[3]
assoc_timeout  = sys.argv[4]
config_timeout = sys.argv[5]

bus_loop = dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus(mainloop=bus_loop)
manager = dbus.Interface(bus.get_object("org.moblin.connman", "/"),
    "org.moblin.connman.Manager")

try:
    path = manager.GetService(({
        "Type": "wifi",
        "Mode": "managed",
        "SSID": ssid,
        "Security": security,
        "Passphrase": psk }))
    service = dbus.Interface(
        bus.get_object("org.moblin.connman", path),
        "org.moblin.connman.Service")
except Exception, e:
    print "FAIL(GetService): ssid %s exception %s" %(ssid, e)
    sys.exit(1)

try:
    service.Connect()
except Exception, e:
    print "FAIL(Connect): ssid %s exception %s" %(ssid, e)
    sys.exit(2)

status = ""
assoc_time = 0
# wait up to assoc_timeout seconds to associate
while assoc_time < assoc_timeout:
    properties = service.GetProperties()
    status = properties.get("State", None)
#    print>>sys.stderr, "time %3.1f state %s" % (assoc_time, status)
    if status == "failure":
        print "FAIL(assoc): ssid %s assoc %3.1f secs props %s" \
        %(ssid, assoc_time, properties)
        sys.exit(3)
    if status == "configuration" or status == "ready":
        break
    time.sleep(.5)
    assoc_time += .5
if assoc_time >= assoc_timeout:
    print "TIMEOUT(assoc): ssid %s assoc %3.1f secs" %(ssid, assoc_time)
    sys.exit(4)

# wait another config_timeout seconds to get an ip address
config_time = 0
if status != "ready":
    while config_time < config_timeout:
        properties = service.GetProperties()
        status = properties.get("State", None)
#        print>>sys.stderr, "time %3.1f state %s" % (config_time, status)
        if status == "failure":
            print "FAIL(config): ssid %s assoc %3.1f config %3.1f secs" \
                %(ssid, assoc_time, config_time)
            sys.exit(5)
        if status == "ready":
            break
        time.sleep(.5)
        config_time += .5
    if config_time >= config_timeout:
        print "TIMEOUT(config): ssid %s assoc %3.1f config %3.1f secs" \
            %(ssid, assoc_time, config_time)
        sys.exit(6)
print "OK %3.1f %3.1f (assoc and config times in sec)" % (assoc_time, config_time)
sys.exit(0)

