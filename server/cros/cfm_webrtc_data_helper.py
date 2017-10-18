"""Helper class for WebRTC data tests."""

import json

import enum

from autotest_lib.server.cros import cfm_jmidata_helper_base


# Stream Type
AUDIO_SENT_LEVEL = u'audio_sent_energy_level'
AUDIO_RECEIVED_LEVEL = u'audio_received_energy_level'
AUDIO_SENT_BYTES = u'audio_sent_bytes'
AUDIO_RECEIVED_BYTES = u'audio_received_bytes'
VIDEO_SENT_BYTES = u'video_sent_bytes'
VIDEO_RECEIVED_BYTES = u'video_received_bytes'
FRAMERATE_RECEIVED = u'framerate_received'
FRAMERATE_DECODED = u'framerate_decoded'
VIDEO_RECEIVED_FRAME_HEIGHT = u'video_received_frame_height'
VIDEO_RECEIVED_FRAME_WIDTH = u'video_received_frame_width'
VIDEO_SENT_FRAME_WIDTH = u'video_sent_frame_width'
VIDEO_SENT_FRAME_HEIGHT = u'video_sent_frame_height'
ACTIVE_INCOMING_VIDEO_STREAMS = u'number_of_active_incoming_video_streams'

# Start index in the JSON object that contains Audio/Video streams related info.
AV_INDEX = 1

SSRC = u'ssrc'
GLOBAL = u'global'


class CpuUsageType(enum.Enum):
    """
    CPU Usage types.
    """
    TOTAL_CPU = u'cpu_percent_of_total'
    BROWSER_CPU = u'browser_cpu_percent_of_total'
    GPU_CPU = u'gpu_percent_of_total'
    NACL_EFFECTS_CPU = u'nacl_effects_cpu_percent_of_total'
    RENDERER_CPU = u'renderer_cpu_percent_of_total'


class WebRTCDataHelper(cfm_jmidata_helper_base.JMIDataHelperBase):
    """
    This class helps in extracting relevant Web RTC data from javascript log.

    The class takes javascript file as input and extracts webrtc stat elements
    from the file that is internally stored as a list. The class uses the JMI
    Data Helper Base class to build on. Whenever we need to extract data, this
    method converts each string element in the internal list to a json object
    and retreives the relevant info from it which is then stored and returned as
    a list.
    """
    # Mostly simple and self-explanatory methods, disable missing-docstring.
    # pylint: disable=missing-docstring

    def __init__(self, log_file_content):
        super(WebRTCDataHelper, self).__init__(log_file_content,
                                               'webrtc_media_stats')

    def _ExtractAllDataPointsWithKey(self, data_type, key):
        """
        Extracts all values from the data points with the given key.

        Args:
            data_type: Type of data we want to pull, SSRC, GLOBAL.
            key: The key for the data to retrieve

        Returns:
            List of all data values, matching the given key, found in the log
        """
        data_list = []
        for data_point in self._jmi_list:
            json_arr = json.loads(data_point)
            for element in json_arr[AV_INDEX:]:
                if element and data_type in element:
                    data_obj = element[data_type]
                    if key in data_obj:
                        data_list.append(int(data_obj[key]))
        return data_list

    def GetAudioReceivedBytesList(self):
        return self._ExtractAllDataPointsWithKey(
                data_type=SSRC, key=AUDIO_RECEIVED_BYTES)

    def GetAudioSentBytesList(self):
        return self._ExtractAllDataPointsWithKey(
                data_type=SSRC, key=AUDIO_SENT_BYTES)

    def GetVideoSentBytesList(self):
        return self._ExtractAllDataPointsWithKey(
                data_type=SSRC, key=VIDEO_SENT_BYTES)

    def GetVideoReceivedBytesList(self):
        return self._ExtractAllDataPointsWithKey(
                data_type=SSRC, key=VIDEO_RECEIVED_BYTES)

    def GetAudioReceivedEnergyList(self):
        return self._ExtractAllDataPointsWithKey(
                data_type=SSRC, key=AUDIO_RECEIVED_LEVEL)

    def GetAudioSentEnergyList(self):
        return self._ExtractAllDataPointsWithKey(
                data_type=SSRC, key=AUDIO_SENT_LEVEL)

    def GetVideoIncomingFramerateReceivedList(self):
        return self._ExtractAllDataPointsWithKey(
                data_type=SSRC, key=FRAMERATE_RECEIVED)

    def GetVideoIncomingFramerateDecodedList(self):
        return self._ExtractAllDataPointsWithKey(
                data_type=SSRC, key=FRAMERATE_DECODED)

    def GetVideoReceivedFrameWidthList(self):
        return self._ExtractAllDataPointsWithKey(
                data_type=SSRC, key=VIDEO_RECEIVED_FRAME_WIDTH)

    def GetVideoReceivedFrameHeightList(self):
        return self._ExtractAllDataPointsWithKey(
                data_type=SSRC, key=VIDEO_RECEIVED_FRAME_HEIGHT)

    def GetVideoSentFrameWidthList(self):
        return self._ExtractAllDataPointsWithKey(
                data_type=SSRC, key=VIDEO_SENT_FRAME_WIDTH)

    def GetVideoSentFrameHeightList(self):
        return self._ExtractAllDataPointsWithKey(
                data_type=SSRC, key=VIDEO_SENT_FRAME_HEIGHT)

    def GetNumberOfActiveIncomingVideoStreams(self):
        """Retrieve number of active incoming video streams."""
        return self._ExtractAllDataPointsWithKey(
                data_type=GLOBAL, key=ACTIVE_INCOMING_VIDEO_STREAMS)

    def GetCpuUsageList(self, cpu_type):
        """
        Retrieves cpu usage data from WebRTC data.

        Args:
            cpu_type: Enum of type CpuUsageType.

        Returns:
            List containing CPU usage data.
        """
        data_list = []
        for data_point in self._jmi_list:
            json_arr = json.loads(data_point)
            for element in json_arr[AV_INDEX:]:
                if element and GLOBAL in element:
                    global_obj = element[GLOBAL]
                    if (cpu_type.value in global_obj and
                            IsFloat(global_obj[cpu_type.value])):
                        data_list.append(float(global_obj[cpu_type.value]))
        return data_list

    def GetTotalCpuPercentage(self):
        return self.GetCpuUsageList(CpuUsageType.TOTAL_CPU)

    def GetBrowserCpuPercentage(self):
        return self.GetCpuUsageList(CpuUsageType.BROWSER_CPU)

    def GetGpuCpuPercentage(self):
        return self.GetCpuUsageList(CpuUsageType.GPU_CPU)

    def GetNaclEffectsCpuPercentage(self):
        return self.GetCpuUsageList(CpuUsageType.NACL_EFFECTS_CPU)

    def GetRendererCpuPercentage(self):
        return self.GetCpuUsageList(CpuUsageType.RENDERER_CPU)


def IsFloat(value):
    """
    Checks if a string value can be converted to a float.
    """
    try:
        float(value)
        return True
    except TypeError:
        return False
