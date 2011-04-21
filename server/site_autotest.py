import os
from autotest_lib.client.common_lib import global_config
from autotest_lib.server import autoserv_parser, installable_object


config = global_config.global_config
parser = autoserv_parser.autoserv_parser


class SiteAutotest(installable_object.InstallableObject):

    def get(self, location = None):
        if not location:
            location = os.path.join(self.serverdir, '../client')
            location = os.path.abspath(location)
        installable_object.InstallableObject.get(self, location)
        self.got = True


    def get_fetch_location(self):
        if not parser.options.image:
            return super(SiteAutotest, self).get_fetch_location()

        repos = config.get_config_value('PACKAGES', 'fetch_location', type=list,
                                        default=[])
        new_repos = []
        for repo in repos[::-1]:
            if repo.endswith('static/archive'):
                path = parser.options.image.rstrip('/')
                build = '/'.join(path.split('/')[-2:])
                repo += '/%s/autotest' % build
            new_repos.append(repo)
        return new_repos


class _SiteRun(object):
    pass
