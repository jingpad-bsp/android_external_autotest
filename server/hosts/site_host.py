from autotest_lib.server import autoserv_parser


parser = autoserv_parser.autoserv_parser


class SiteHost():
    def machine_install(self):
        image = parser.options.image
        print "Install %s to host: %s" % (image, self.hostname)
        # TODO(seano): implement the real os reimage method here.

