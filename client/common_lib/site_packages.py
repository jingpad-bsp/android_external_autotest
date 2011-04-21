from autotest_lib.client.common_lib import base_packages


class SiteHttpFetcher(base_packages.HttpFetcher):
    # shortcut quick http test for now since our dev server does not support
    # this operation.
    def _quick_http_test(self):
        return


class SitePackageManager(base_packages.BasePackageManager):
    def get_fetcher(self, url):
        if url.startswith('http://'):
            return SiteHttpFetcher(self, url)
        else:
            return super(SitePackageManager, self).get_fetcher(url)
