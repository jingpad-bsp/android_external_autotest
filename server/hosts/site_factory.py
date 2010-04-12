from autotest_lib.server import autoserv_parser
from autotest_lib.server.hosts import chromiumos_host

def postprocess_classes(classes, hostname, **args):
    """Site-specific processing of the class list."""

    classes.append(chromiumos_host.ChromiumOSHost)
