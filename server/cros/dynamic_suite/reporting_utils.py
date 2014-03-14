import json
import logging

import common

from autotest_lib.client.common_lib import autotemp
from autotest_lib.client.common_lib import global_config


# Try importing the essential bug reporting libraries. Chromite and gdata_lib
# are useless unless they can import gdata too.
try:
    __import__('chromite')
    __import__('gdata')
except ImportError, e:
    fundamental_libs = False
    logging.debug('Will not be able to generate link '
                  'to the buildbot page when filing bugs. %s', e)
else:
    from chromite.lib import cros_build_lib, gs
    fundamental_libs = True


# Number of times to retry if a gs command fails. Defaults to 10,
# which is far too long given that we already wait on these files
# before starting HWTests.
_GS_RETRIES = 1


_HTTP_ERROR_THRESHOLD = 400
BUG_CONFIG_SECTION = 'BUG_REPORTING'


# global configurations needed for build artifacts
_gs_domain = global_config.global_config.get_config_value(
    BUG_CONFIG_SECTION, 'gs_domain', default='')
_chromeos_image_archive = global_config.global_config.get_config_value(
    BUG_CONFIG_SECTION, 'chromeos_image_archive', default='')
_arg_prefix = global_config.global_config.get_config_value(
    BUG_CONFIG_SECTION, 'arg_prefix', default='')


# global configurations needed for results log
_retrieve_logs_cgi = global_config.global_config.get_config_value(
    BUG_CONFIG_SECTION, 'retrieve_logs_cgi', default='')
_generic_results_bin = global_config.global_config.get_config_value(
    BUG_CONFIG_SECTION, 'generic_results_bin', default='')
_debug_dir = global_config.global_config.get_config_value(
    BUG_CONFIG_SECTION, 'debug_dir', default='')


# Template for the url used to generate the link to the job
_job_view = global_config.global_config.get_config_value(
    BUG_CONFIG_SECTION, 'job_view', default='')


# gs prefix to perform file like operations (gs://)
_gs_file_prefix = global_config.global_config.get_config_value(
    BUG_CONFIG_SECTION, 'gs_file_prefix', default='')


# global configurations needed for buildbot stages link
_buildbot_builders = global_config.global_config.get_config_value(
    BUG_CONFIG_SECTION, 'buildbot_builders', default='')
_build_prefix = global_config.global_config.get_config_value(
    BUG_CONFIG_SECTION, 'build_prefix', default='')



def link_build_artifacts(build):
    """Returns a url to build artifacts on google storage.

    @param build: A string, e.g. stout32-release/R30-4433.0.0

    @returns: A url to build artifacts on google storage.

    """
    return (_gs_domain + _arg_prefix +
            _chromeos_image_archive + build)


def link_job(job_id, instance_server=None):
    """Returns an url to the job on cautotest.

    @param job_id: A string, representing the job id.
    @param instance_server: The instance server.
        Eg: cautotest, cautotest-cq, localhost.

    @returns: An url to the job on cautotest.

    """
    if not job_id:
        return 'Job did not run, or was aborted prematurely'
    if not instance_server:
        instance_server = global_config.global_config.get_config_value(
            'SERVER', 'hostname', default='localhost')
    if 'cautotest' in instance_server:
        instance_server += '.corp.google.com'
    return _job_view % (instance_server, job_id)


def _base_results_log(job_id, result_owner, hostname):
    """Returns the base url of the job's results.

    @param job_id: A string, representing the job id.
    @param result_owner: A string, representing the onwer of the job.
    @param hostname: A string, representing the host on which
                     the job has run.

    @returns: The base url of the job's results.

    """
    if job_id and result_owner and hostname:
        path_to_object = '%s-%s/%s' % (job_id, result_owner,
                                       hostname)
        return (_retrieve_logs_cgi + _generic_results_bin +
                path_to_object)


def link_result_logs(job_id, result_owner, hostname):
    """Returns a url to test logs on google storage.

    @param job_id: A string, representing the job id.
    @param result_owner: A string, representing the owner of the job.
    @param hostname: A string, representing the host on which the
                     jot has run.

    @returns: A url to test logs on google storage.

    """
    base_results = _base_results_log(job_id, result_owner, hostname)
    if base_results:
        return '%s/%s' % (base_results, _debug_dir)
    return ('Could not generate results log: the job with id %s, '
            'scheduled by: %s on host: %s did not run' %
            (job_id, result_owner, hostname))


def link_status_log(job_id, result_owner, hostname):
    """Returns an url to status log of the job.

    @param job_id: A string, representing the job id.
    @param result_owner: A string, representing the owner of the job.
    @param hostname: A string, representing the host on which the
                     jot has run.

    @returns: A url to status log of the job.

    """
    base_results = _base_results_log(job_id, result_owner, hostname)
    if base_results:
        return '%s/%s' % (base_results, 'status.log')
    return 'NA'


def _get_metadata_dict(build):
    """
    Get a dictionary of metadata related to this failure.

    Metadata.json is created in the HWTest Archiving stage, if this file
    isn't found the call to Cat will timeout after the number of retries
    specified in the GSContext object. If metadata.json exists we parse
    a json string of it's contents into a dictionary, which we return.

    @param build: A string, e.g. stout32-release/R30-4433.0.0

    @returns: A dictionary with the contents of metadata.json.

    """
    if not fundamental_libs:
        return
    try:
        tempdir = autotemp.tempdir()
        gs_context = gs.GSContext(retries=_GS_RETRIES,
                                  cache_dir=tempdir.name)
        gs_cmd = '%s%s%s/metadata.json' % (_gs_file_prefix,
                                           _chromeos_image_archive,
                                           build)
        return json.loads(gs_context.Cat(gs_cmd).output)
    except (cros_build_lib.RunCommandError, gs.GSContextException) as e:
        logging.debug(e)
    finally:
        tempdir.clean()


def link_buildbot_stages(build):
    """
    Link to the buildbot page associated with this run of HWTests.

    @param build: A string, e.g. stout32-release/R30-4433.0.0

    @return: A link to the buildbot stages page, or 'NA' if we cannot glean
             enough information from metadata.json (or it doesn't exist).
    """
    metadata = _get_metadata_dict(build)
    if (metadata and
        metadata.get('builder-name') and
        metadata.get('build-number')):

        return ('%s%s/builds/%s' %
                    (_buildbot_builders,
                     metadata.get('builder-name'),
                     metadata.get('build-number'))).replace(' ', '%20')
    return 'NA'
