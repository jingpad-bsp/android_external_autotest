import dbus, dbus.mainloop.glib, gobject, logging, re, sys, time, subprocess

ssid           = sys.argv[1]
security       = sys.argv[2]
psk            = sys.argv[3]
assoc_timeout  = float(sys.argv[4])
config_timeout = float(sys.argv[5])
reset_timeout  = float(sys.argv[6]) if len(sys.argv) > 6 else assoc_timeout

FLIMFLAM = "org.chromium.flimflam"

bus_loop = dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus(mainloop=bus_loop)
manager = dbus.Interface(bus.get_object(FLIMFLAM, "/"), FLIMFLAM + ".Manager")
connect_quirks = {}

connection_settings = {
   "Type": "wifi",
   "Mode": "managed",
   "SSID": ssid,
   "Security": security
}

if security == '802_1x':
    (connection_settings["Identity"],
     connection_settings["CertPath"]) = psk.split(':')
else:
   connection_settings["Passphrase"] = psk


def DbusSetup():
    try:
        path = manager.GetService((connection_settings))
        service = dbus.Interface(
            bus.get_object(FLIMFLAM, path), FLIMFLAM + ".Service")
    except Exception, e:
        print "FAIL(GetService): ssid %s exception %s" % (ssid, e)
        ErrExit(1)

    return (path, service)


def ParseProps(props):
    proplist = []
    if props is not None:
        for p in props:
            proplist.append("'%s': '%s'" % (str(p), str(props[p])))
        return '{ %s }' % ', '.join(proplist)
    else:
        return 'None'


def ResetService(init_state):
    wait_time = 0

    if init_state == 'idle':
        # If we are already idle, we have nothing to do
        return
    if init_state == 'ready':
        # flimflam is already connected.  Disconnect.
        connect_quirks['already_connected'] = 1
        service.Disconnect()
    else:
        # Workaround to force flimflam out of error state and back to 'idle'
        connect_quirks['clear_error'] = 1
        service.ClearProperty('Error')

    while wait_time < reset_timeout:
        if service.GetProperties().get("State", None) == "idle":
            break
        time.sleep(2)
        wait_time += 2

    print>>sys.stderr, "cleared ourselves out of '%s' after %3.1f secs" % \
        (init_state, wait_time)
    time.sleep(4)


def TryConnect(assoc_time):
    init_assoc_time = assoc_time
    try:
        init_props = service.GetProperties()
        init_state = init_props.get("State", None)
        if init_state == "configuration" or init_state == "ready":
            if assoc_time > 0:
                # We connected in the time between the last failure and now
                print>>sys.stderr, "Associated while we weren't looking!"
                return (init_props, None)
    except dbus.exceptions.DBusException, e:
        connect_quirks['lost_dbus'] = 1
        print>>sys.stderr, "We just lost the service handle!"
        return (None, 'DBUSFAIL')

    ResetService(init_state)

    # print "INIT_STATUS1: %s" % service.GetProperties().get("State", None)

    try:
        service.Connect()
    except dbus.exceptions.DBusException, e:
        if e.get_dbus_name() ==  'org.chromium.flimflam.Error.InProgress':
            # We can hope that a ResetService in the next call will solve this
            connect_quirks['in_progress'] = 1
            print>>sys.stderr, "Previous connect is still in progress!"
            time.sleep(5)
            return (None, 'FAIL')
        if e.get_dbus_name() ==  'org.freedesktop.DBus.Error.UnknownMethod':
            # We can hope that a ResetService in the next call will solve this
            connect_quirks['lost_dbus_connect'] = 1
            print>>sys.stderr, "Lost the service handle during Connect()!"
            time.sleep(0.5)
            return (None, 'FAIL')
        # What is this exception?
        print "FAIL(Connect): ssid %s DBus exception %s" %(ssid, e)
        ErrExit(2)
    except Exception, e:
        print "FAIL(Connect): ssid %s exception %s" %(ssid, e)
        ErrExit(2)

    properties = None
    # wait up to assoc_timeout seconds to associate
    while assoc_time < assoc_timeout:
        try:
            properties = service.GetProperties()
        except dbus.exceptions.DBusException, e:
            connect_quirks['get_prop'] = 1
            print>>sys.stderr, "Got exception trying GetProperties(): %s" % e
            return (None, 'DBUSFAIL')
        status = properties.get("State", None)
        #    print>>sys.stderr, "time %3.1f state %s" % (assoc_time, status)
        if status == "failure":
            if assoc_time == init_assoc_time:
                connect_quirks['fast_fail'] = 1
                print>>sys.stderr, "failure on first try!  Sleep 5 seconds"
                time.sleep(5)
            return (properties, 'FAIL')
        if status == "configuration" or status == "ready":
            return (properties, None)
        time.sleep(.5)
        assoc_time += .5
    if assoc_time >= assoc_timeout:
        if properties is None:
            properties = service.GetProperties()
        return (properties, 'TIMEOUT')


# Open /var/log/messages and seek to the current end
def OpenLogs(*logfiles):
    logs = []
    for logfile in logfiles:
        try:
            msgs = open(logfile)
            msgs.seek(0, 2)
            logs.append({ 'name': logfile, 'file': msgs })
        except Exception, e:
            # If we cannot open the file, this is not necessarily an error
            pass

    return logs


def DumpObjectList(kind):
    print>>sys.stderr, "%s list:" % kind
    for item in [dbus.Interface(bus.get_object(FLIMFLAM, path),
                                FLIMFLAM + "." + kind)
                 for path in manager.GetProperties().get(kind + 's', [])]:
        print>>sys.stderr, "[ %s ]" % (item.object_path)
        for key, val in item.GetProperties().items():
            print>>sys.stderr, "    %s = %s" % (key, str(val))

# Returns the list of the wifi interfaces (e.g. "wlan0") known to flimflam
def GetWifiInterfaces():
    interfaces = []
    device_paths = manager.GetProperties().get("Devices", None)
    for device_path in device_paths:
        device = dbus.Interface(
            bus.get_object("org.chromium.flimflam", device_path),
            "org.chromium.flimflam.Device")
        props = device.GetProperties()
        type = props.get("Type", None)
        interface = props.get("Interface", None)
        if type == "wifi":
            interfaces.append(interface)
    return interfaces

def DumpLogs(logs):
    for log in logs:
        print>>sys.stderr, "Content of %s during our run:" % log['name']
        print>>sys.stderr, "  )))  ".join(log['file'].readlines())

    for interface in GetWifiInterfaces():
        print>>sys.stderr, "iw dev %s scan output: %s" % \
            ( interface,
              subprocess.Popen(["iw", "dev", interface, "scan", "dump"],
                               stdout=subprocess.PIPE).communicate()[0])

    DumpObjectList("Service")

def ErrExit(code):
    try:
        service.Disconnect()
    except:
        pass
    DumpLogs(logs)
    sys.exit(code)

logs = OpenLogs('/var/log/messages', '/var/log/hostap.log')

(path, service) = DbusSetup()

assoc_start = time.time()
for attempt in range(5):
    assoc_time = time.time() - assoc_start
    print>>sys.stderr, "connect attempt #%d %3.1f secs" % (attempt, assoc_time)
    (properties, failure_type) = TryConnect(assoc_time)
    if failure_type is None or failure_type == 'TIMEOUT':
        break
    if failure_type == 'DBUSFAIL':
        (path, service) = DbusSetup()

assoc_time = time.time() - assoc_start

if attempt > 0:
    connect_quirks['multiple_attempts'] = 1

if failure_type is not None:
    print "%s(assoc): ssid %s assoc %3.1f secs props %s" \
        %(failure_type, ssid, assoc_time, ParseProps(properties))
    ErrExit(3)

# wait another config_timeout seconds to get an ip address
config_time = 0
status = properties.get("State", None)
if status != "ready":
    while config_time < config_timeout:
        properties = service.GetProperties()
        status = properties.get("State", None)
#        print>>sys.stderr, "time %3.1f state %s" % (config_time, status)
        if status == "failure":
            print "FAIL(config): ssid %s assoc %3.1f config %3.1f secs" \
                %(ssid, assoc_time, config_time)
            ErrExit(5)
        if status == "ready":
            break
        if status != "configuration":
            print "FAIL(config): ssid %s assoc %3.1f config %3.1f secs *%s*" \
                %(ssid, assoc_time, config_time, status)
            ErrExit(4)
        time.sleep(.5)
        config_time += .5
    if config_time >= config_timeout:
        print "TIMEOUT(config): ssid %s assoc %3.1f config %3.1f secs" \
            %(ssid, assoc_time, config_time)
        ErrExit(6)

print "OK %3.1f %3.1f %s (assoc and config times in sec, quirks)" \
    %(assoc_time, config_time, str(connect_quirks.keys()))

if connect_quirks:
    DumpLogs(logs)
sys.exit(0)
