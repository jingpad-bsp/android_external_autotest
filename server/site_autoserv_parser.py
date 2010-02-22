__author__ = "raphtee@google.com (Travis Miller)"
__author__ = "ericli@chromium.com (Eric Li)"

import common
from autotest_lib.server.autoserv_parser import base_autoserv_parser


add_usage = """\
"""


class site_autoserv_parser(base_autoserv_parser):
    def get_usage(self):
        usage = super(site_autoserv_parser, self).get_usage()
        return usage+add_usage


    def setup_options(self):
        base_autoserv_parser.setup_options(self)
        self.parser.add_option("--image", action="store", type="string",
                               dest="image",
                               help="Full path of an osimage to install.")   


    def parse_args(self):
        base_autoserv_parser.parse_args(self)
        if self.options.image:
            self.options.install_before = True

