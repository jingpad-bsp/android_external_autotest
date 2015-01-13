#!/usr/bin/python

import cgi, os, sys, urllib2
import common
from autotest_lib.frontend import setup_django_environment

from autotest_lib.client.common_lib import global_config
from autotest_lib.client.bin import utils
from autotest_lib.frontend.afe.json_rpc import serviceHandler
from autotest_lib.site_utils import server_manager_utils

_PAGE = """\
Status: 302 Found
Content-Type: text/plain
Location: %s\r\n\r
"""

GOOGLE_STORAGE_PATTERN = 'storage.cloud.google.com/'

# Define function for retrieving logs
def _retrieve_logs_dummy(job_path):
    pass

site_retrieve_logs = utils.import_site_function(__file__,
    "autotest_lib.tko.site_retrieve_logs", "site_retrieve_logs",
    _retrieve_logs_dummy)

site_find_repository_host = utils.import_site_function(__file__,
    "autotest_lib.tko.site_retrieve_logs", "site_find_repository_host",
    _retrieve_logs_dummy)


form = cgi.FieldStorage(keep_blank_values=True)
# determine if this is a JSON-RPC request.  we support both so that the new TKO
# client can use its RPC client code, but the old TKO can still use simple GET
# params.
_is_json_request = form.has_key('callback')

def _get_requested_path():
    if _is_json_request:
        request_data = form['request'].value
        request = serviceHandler.ServiceHandler.translateRequest(request_data)
        parameters = request['params'][0]
        return parameters['path']

    return form['job'].value


def find_repository_host(job_path):
    """Find the machine holding the given logs and return a URL to the logs"""
    site_repo_info = site_find_repository_host(job_path)
    if site_repo_info is not None:
        return site_repo_info

    config = global_config.global_config
    if server_manager_utils.use_server_db():
        drones = server_manager_utils.get_drones()
    else:
        drones = config.get_config_value('SCHEDULER', 'drones').split(',')

    # TODO: This won't scale as we add more shards. Ideally the frontend would
    # pipe the shard_hostname with the job_id but there are helper scripts like
    # dut_history that hit the main cautotest frontend for logs. For these, it
    # is easier to handle the shard translation internally just like we do with
    # drones.
    shards = config.get_config_value('SERVER', 'shards', default='')
    results_host = config.get_config_value('SCHEDULER', 'results_host')
    archive_host = config.get_config_value('SCHEDULER', 'archive_host',
                                            default='')
    results_repos = [results_host]
    for host in drones + shards.split(','):
        host = host.strip()
        if host and host not in results_repos:
            results_repos.append(host)

    if archive_host and archive_host not in results_repos:
        results_repos.append(archive_host)

    for drone in results_repos:
        if drone == 'localhost':
            continue
        http_path = 'http://%s%s' % (drone, job_path)
        try:
            utils.urlopen(http_path)

            # On Vms the shard name is set to the default gateway but the
            # browser used to navigate frontends (that runs on the host of
            # the vms) is immune to the same NAT routing the vms have, so we
            # need to replace the gateway with 'localhost'.
            if utils.DEFAULT_VM_GATEWAY in drone:
                drone = drone.replace(utils.DEFAULT_VM_GATEWAY, 'localhost')
            else:
                drone = utils.normalize_hostname(drone)
            return 'http', drone, job_path
        except urllib2.URLError:
            pass

    # If the URL requested is a test result, it is now either on the local
    # host or in Google Storage.
    if job_path.startswith('/results/'):
        # We only care about the path after '/results/'.
        job_relative_path = job_path[9:]
        if not os.path.exists(os.path.join('/usr/local/autotest/results',
                                           job_relative_path)):
            gsuri = utils.get_offload_gsuri().split('gs://')[1]
            return ['https', GOOGLE_STORAGE_PATTERN, gsuri + job_relative_path]


def get_full_url(info, log_path):
    if info is not None:
        protocol, host, path = info
        prefix = '%s://%s' % (protocol, host)
    else:
        prefix = ''
        path = log_path

    if _is_json_request:
        return '%s/tko/jsonp_fetcher.cgi?%s' % (prefix,
                                                os.environ['QUERY_STRING'])
    else:
        return prefix + path


log_path = _get_requested_path()
info = find_repository_host(log_path)
site_retrieve_logs(log_path)
print _PAGE % get_full_url(info, log_path)
