# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
This module provides bindings for ModemManager1 DBus constants, such as
interface names, enumerations, and errors.

"""

import dbus.exceptions

# The ModemManager1 Object
MM1 = '/org/freedesktop/ModemManager1'

# The Root Object Path
ROOT_PATH = '/'

# Interfaces
# Standard Interfaces
I_PROPERTIES = 'org.freedesktop.DBus.Properties'
I_INTROSPECTABLE = 'org.freedesktop.DBus.Introspectable'
I_OBJECT_MANAGER = 'org.freedesktop.DBus.ObjectManager'

# ModemManager1
I_MODEM_MANAGER = 'org.freedesktop.ModemManager1'

# Modems
I_MODEM = I_MODEM_MANAGER + '.Modem'
I_MODEM_SIMPLE = I_MODEM + '.Simple'
I_MODEM_3GPP = I_MODEM + '.Modem3gpp'
I_MODEM_3GPP_USSD = I_MODEM_3GPP + '.Ussd'
I_MODEM_CDMA = I_MODEM + '.ModemCdma'
I_MODEM_MESSAGING = I_MODEM + '.Messaging'
I_MODEM_LOCATION = I_MODEM + '.Location'
I_MODEM_TIME = I_MODEM + '.Time'
I_MODEM_FIRMWARE = I_MODEM + '.Firmware'
I_MODEM_CONTACTS = I_MODEM + '.Contacts'

# Bearers
I_BEARER = I_MODEM_MANAGER + '.Bearer'

# SIMs
I_SIM = I_MODEM_MANAGER + '.Sim'

# SMSs
I_SMS = I_MODEM_MANAGER + '.Sms'


# Common Types
# Flags and Enumerations

# enum MMBearerIpFamily
MM_BEARER_IP_FAMILY_UNKNOWN = 0
MM_BEARER_IP_FAMILY_IPV4 = 4
MM_BEARER_IP_FAMILY_IPV6 = 6
MM_BEARER_IP_FAMILY_IPV4V6 = 10

# enum MMBearerIpMethod
MM_BEARER_IP_METHOD_UNKNOWN = 0,
MM_BEARER_IP_METHOD_PPP = 1,
MM_BEARER_IP_METHOD_STATIC = 2,
MM_BEARER_IP_METHOD_DHCP = 3

# enum MMModem3gppFacility
MM_MODEM_3GPP_FACILITY_NONE = 0
MM_MODEM_3GPP_FACILITY_SIM = 1 << 0
MM_MODEM_3GPP_FACILITY_FIXED_DIALING = 1 << 1
MM_MODEM_3GPP_FACILITY_PH_SIM = 1 << 2
MM_MODEM_3GPP_FACILITY_PH_FSIM = 1 << 3
MM_MODEM_3GPP_FACILITY_NET_PERS = 1 << 4
MM_MODEM_3GPP_FACILITY_NET_SUB_PERS = 1 << 5
MM_MODEM_3GPP_FACILITY_PROVIDER_PERS = 1 << 6
MM_MODEM_3GPP_FACILITY_CORP_PERS = 1 << 7

# enum MMModem3gppNetworkAvailability
MM_MODEM_3GPP_NETWORK_AVAILABILITY_UNKNOWN = 0
MM_MODEM_3GPP_NETWORK_AVAILABILITY_AVAILABLE = 1
MM_MODEM_3GPP_NETWORK_AVAILABILITY_CURRENT = 2
MM_MODEM_3GPP_NETWORK_AVAILABILITY_FORBIDDEN = 3

# enum MMModem3gppRegistrationState
MM_MODEM_3GPP_REGISTRATION_STATE_IDLE = 0
MM_MODEM_3GPP_REGISTRATION_STATE_HOME = 1
MM_MODEM_3GPP_REGISTRATION_STATE_SEARCHING = 2
MM_MODEM_3GPP_REGISTRATION_STATE_DENIED = 3
MM_MODEM_3GPP_REGISTRATION_STATE_UNKNOWN = 4
MM_MODEM_3GPP_REGISTRATION_STATE_ROAMING = 5

REGISTRATION_STATE_STRINGS = [
    'IDLE',
    'HOME',
    'SEARCHING',
    'DENIED',
    'UNKNOWN',
    'ROAMING'
]

def RegistrationStateToString(state):
    return REGISTRATION_STATE_STRINGS[state]

# enum MMModem3gppUssdSessionState
MM_MODEM_3GPP_USSD_SESSION_STATE_UNKNOWN = 0
MM_MODEM_3GPP_USSD_SESSION_STATE_IDLE = 1
MM_MODEM_3GPP_USSD_SESSION_STATE_ACTIVE = 2
MM_MODEM_3GPP_USSD_SESSION_STATE_USER_RESPONSE = 3

# enum MMModemAccessTechnology
MM_MODEM_ACCESS_TECHNOLOGY_UNKNOWN = 0
MM_MODEM_ACCESS_TECHNOLOGY_POTS = 1 << 0
MM_MODEM_ACCESS_TECHNOLOGY_GSM = 1 << 1
MM_MODEM_ACCESS_TECHNOLOGY_GSM_COMPACT = 1 << 2
MM_MODEM_ACCESS_TECHNOLOGY_GPRS = 1 << 3
MM_MODEM_ACCESS_TECHNOLOGY_EDGE = 1 << 4
MM_MODEM_ACCESS_TECHNOLOGY_UMTS = 1 << 5
MM_MODEM_ACCESS_TECHNOLOGY_HSDPA = 1 << 6
MM_MODEM_ACCESS_TECHNOLOGY_HSUPA = 1 << 7
MM_MODEM_ACCESS_TECHNOLOGY_HSPA = 1 << 8
MM_MODEM_ACCESS_TECHNOLOGY_HSPA_PLUS = 1 << 9
MM_MODEM_ACCESS_TECHNOLOGY_1XRTT = 1 << 10
MM_MODEM_ACCESS_TECHNOLOGY_EVDO0 = 1 << 11
MM_MODEM_ACCESS_TECHNOLOGY_EVDOA = 1 << 12
MM_MODEM_ACCESS_TECHNOLOGY_EVDOB = 1 << 13
MM_MODEM_ACCESS_TECHNOLOGY_LTE = 1 << 14
MM_MODEM_ACCESS_TECHNOLOGY_ANY = 0xFFFFFFFF

# enum MMModemBand
MM_MODEM_BAND_UNKNOWN = 0
# GSM/UMTS bands
MM_MODEM_BAND_EGSM = 1
MM_MODEM_BAND_DCS = 2
MM_MODEM_BAND_PCS = 3
MM_MODEM_BAND_G850 = 4
MM_MODEM_BAND_U2100 = 5
MM_MODEM_BAND_U1800 = 6
MM_MODEM_BAND_U17IV = 7
MM_MODEM_BAND_U800 = 8
MM_MODEM_BAND_U850 = 9
MM_MODEM_BAND_U900 = 10
MM_MODEM_BAND_U17IX = 11
MM_MODEM_BAND_U1900 = 12
MM_MODEM_BAND_U2600 = 13
# LTE bands
MM_MODEM_BAND_EUTRAN_I = 31
MM_MODEM_BAND_EUTRAN_II = 32
MM_MODEM_BAND_EUTRAN_III = 33
MM_MODEM_BAND_EUTRAN_IV = 34
MM_MODEM_BAND_EUTRAN_V = 35
MM_MODEM_BAND_EUTRAN_VI = 36
MM_MODEM_BAND_EUTRAN_VII = 37
MM_MODEM_BAND_EUTRAN_VIII = 38
MM_MODEM_BAND_EUTRAN_IX = 39
MM_MODEM_BAND_EUTRAN_X = 40
MM_MODEM_BAND_EUTRAN_XI = 41
MM_MODEM_BAND_EUTRAN_XII = 42
MM_MODEM_BAND_EUTRAN_XIII = 43
MM_MODEM_BAND_EUTRAN_XIV = 44
MM_MODEM_BAND_EUTRAN_XVII = 47
MM_MODEM_BAND_EUTRAN_XVIII = 48
MM_MODEM_BAND_EUTRAN_XIX = 49
MM_MODEM_BAND_EUTRAN_XX = 50
MM_MODEM_BAND_EUTRAN_XXI = 51
MM_MODEM_BAND_EUTRAN_XXII = 52
MM_MODEM_BAND_EUTRAN_XXIII = 53
MM_MODEM_BAND_EUTRAN_XXIV = 54
MM_MODEM_BAND_EUTRAN_XXV = 55
MM_MODEM_BAND_EUTRAN_XXVI = 56
MM_MODEM_BAND_EUTRAN_XXXIII = 63
MM_MODEM_BAND_EUTRAN_XXXIV = 64
MM_MODEM_BAND_EUTRAN_XXXV = 65
MM_MODEM_BAND_EUTRAN_XXXVI = 66
MM_MODEM_BAND_EUTRAN_XXXVII = 67
MM_MODEM_BAND_EUTRAN_XXXVIII = 68
MM_MODEM_BAND_EUTRAN_XXXIX = 69
MM_MODEM_BAND_EUTRAN_XL = 70
MM_MODEM_BAND_EUTRAN_XLI = 71
MM_MODEM_BAND_EUTRAN_XLII = 72
MM_MODEM_BAND_EUTRAN_XLIII = 73
# CDMA Band Classes (see 3GPP2 C.S0057-C)
MM_MODEM_BAND_CDMA_BC0_CELLULAR_800 = 128
MM_MODEM_BAND_CDMA_BC1_PCS_1900 = 129
MM_MODEM_BAND_CDMA_BC2_TACS = 130
MM_MODEM_BAND_CDMA_BC3_JTACS = 131
MM_MODEM_BAND_CDMA_BC4_KOREAN_PCS = 132
MM_MODEM_BAND_CDMA_BC5_NMT450 = 134
MM_MODEM_BAND_CDMA_BC6_IMT2000 = 135
MM_MODEM_BAND_CDMA_BC7_CELLULAR_700 = 136
MM_MODEM_BAND_CDMA_BC8_1800 = 137
MM_MODEM_BAND_CDMA_BC9_900 = 138
MM_MODEM_BAND_CDMA_BC10_SECONDARY_800 = 139
MM_MODEM_BAND_CDMA_BC11_PAMR_400 = 140
MM_MODEM_BAND_CDMA_BC12_PAMR_800 = 141
MM_MODEM_BAND_CDMA_BC13_IMT2000_2500 = 142
MM_MODEM_BAND_CDMA_BC14_PCS2_1900 = 143
MM_MODEM_BAND_CDMA_BC15_AWS = 144
MM_MODEM_BAND_CDMA_BC16_US_2500 = 145
MM_MODEM_BAND_CDMA_BC17_US_FLO_2500 = 146
MM_MODEM_BAND_CDMA_BC18_US_PS_700 = 147
MM_MODEM_BAND_CDMA_BC19_US_LOWER_700 = 148
# All/Any
MM_MODEM_BAND_ANY = 256

# enum MMModemCapability
MM_MODEM_CAPABILITY_NONE = 0
MM_MODEM_CAPABILITY_POTS = 1 << 0
MM_MODEM_CAPABILITY_CDMA_EVDO = 1 << 1
MM_MODEM_CAPABILITY_GSM_UMTS = 1 << 2
MM_MODEM_CAPABILITY_LTE = 1 << 3
MM_MODEM_CAPABILITY_LTE_ADVANCED = 1 << 4
MM_MODEM_CAPABILITY_IRIDIUM = 1 << 5

# enum MMModemCdmaActivationState
MM_MODEM_CDMA_ACTIVATION_STATE_UNKNOWN = 0
MM_MODEM_CDMA_ACTIVATION_STATE_NOT_ACTIVATED = 1
MM_MODEM_CDMA_ACTIVATION_STATE_ACTIVATING = 2
MM_MODEM_CDMA_ACTIVATION_STATE_PARTIALLY_ACTIVATED = 3
MM_MODEM_CDMA_ACTIVATION_STATE_ACTIVATED = 4

# enum MMModemCdmaRegistrationState
MM_MODEM_CDMA_REGISTRATION_STATE_UNKNOWN = 0
MM_MODEM_CDMA_REGISTRATION_STATE_REGISTERED = 1
MM_MODEM_CDMA_REGISTRATION_STATE_HOME = 2
MM_MODEM_CDMA_REGISTRATION_STATE_ROAMING = 3

# enum MMModemCdmaRmProtocol
MM_MODEM_CDMA_RM_PROTOCOL_UNKNOWN = 0
MM_MODEM_CDMA_RM_PROTOCOL_ASYNC = 1
MM_MODEM_CDMA_RM_PROTOCOL_PACKET_RELAY = 2
MM_MODEM_CDMA_RM_PROTOCOL_PACKET_NETWORK_PPP = 3
MM_MODEM_CDMA_RM_PROTOCOL_PACKET_NETWORK_SLIP = 4
MM_MODEM_CDMA_RM_PROTOCOL_STU_III = 5

# enum MMModemContactsStorage
MM_MODEM_CONTACTS_STORAGE_UNKNOWN = 0
MM_MODEM_CONTACTS_STORAGE_ME = 1
MM_MODEM_CONTACTS_STORAGE_SM = 2
MM_MODEM_CONTACTS_STORAGE_MT = 3

# enum MMModemLocationSource
MM_MODEM_LOCATION_SOURCE_NONE = 0
MM_MODEM_LOCATION_SOURCE_3GPP_LAC_CI = 1 << 0
MM_MODEM_LOCATION_SOURCE_GPS_RAW = 1 << 1
MM_MODEM_LOCATION_SOURCE_GPS_NMEA = 1 << 2

# enum MMModemLock
MM_MODEM_LOCK_UNKNOWN = 0
MM_MODEM_LOCK_NONE = 1
MM_MODEM_LOCK_SIM_PIN = 2
MM_MODEM_LOCK_SIM_PIN2 = 3
MM_MODEM_LOCK_SIM_PUK = 4
MM_MODEM_LOCK_SIM_PUK2 = 5
MM_MODEM_LOCK_PH_SP_PIN = 6
MM_MODEM_LOCK_PH_SP_PUK = 7
MM_MODEM_LOCK_PH_NET_PIN = 8
MM_MODEM_LOCK_PH_NET_PUK = 9
MM_MODEM_LOCK_PH_SIM_PIN = 10
MM_MODEM_LOCK_PH_CORP_PIN = 11
MM_MODEM_LOCK_PH_CORP_PUK = 12
MM_MODEM_LOCK_PH_FSIM_PIN = 13
MM_MODEM_LOCK_PH_FSIM_PUK = 14
MM_MODEM_LOCK_PH_NETSUB_PIN = 15
MM_MODEM_LOCK_PH_NETSUB_PUK = 16

# enum MMModemMode
MM_MODEM_MODE_NONE = 0
MM_MODEM_MODE_CS = 1 << 0
MM_MODEM_MODE_2G = 1 << 1
MM_MODEM_MODE_3G = 1 << 2
MM_MODEM_MODE_4G = 1 << 3
MM_MODEM_MODE_ANY = 0xFFFFFFFF

# enum MMModemState
MM_MODEM_STATE_FAILED = -1
MM_MODEM_STATE_UNKNOWN = 0
MM_MODEM_STATE_INITIALIZING = 1
MM_MODEM_STATE_LOCKED = 2
MM_MODEM_STATE_DISABLED = 3
MM_MODEM_STATE_DISABLING = 4
MM_MODEM_STATE_ENABLING = 5
MM_MODEM_STATE_ENABLED = 6
MM_MODEM_STATE_SEARCHING = 7
MM_MODEM_STATE_REGISTERED = 8
MM_MODEM_STATE_DISCONNECTING = 9
MM_MODEM_STATE_CONNECTING = 10
MM_MODEM_STATE_CONNECTED = 11

MODEM_STATE_STRINGS = [
    'FAILED',
    'UNKNOWN',
    'INITIALIZING',
    'LOCKED',
    'DISABLED',
    'DISABLING',
    'ENABLING',
    'ENABLED',
    'SEARCHING',
    'REGISTERED',
    'DISCONNECTING',
    'CONNECTING',
    'CONNECTED'
]

def ModemStateToString(state):
    return MODEM_STATE_STRINGS[state + 1]

# enum MMModemPowerState
MM_MODEM_POWER_STATE_UNKNOWN = 0
MM_MODEM_POWER_STATE_OFF = 1
MM_MODEM_POWER_STATE_LOW = 2
MM_MODEM_POWER_STATE_ON = 3

# enum MMModemStateChangeReason
MM_MODEM_STATE_CHANGE_REASON_UNKNOWN = 0
MM_MODEM_STATE_CHANGE_REASON_USER_REQUESTED = 1
MM_MODEM_STATE_CHANGE_REASON_SUSPEND = 2

# enum MMSmsState
MM_SMS_STATE_UNKNOWN = 0
MM_SMS_STATE_STORED = 1
MM_SMS_STATE_RECEIVING = 2
MM_SMS_STATE_RECEIVED = 3
MM_SMS_STATE_SENDING = 4
MM_SMS_STATE_SENT = 5

# enum MMSmsStorage
MM_SMS_STORAGE_UNKNOWN = 0
MM_SMS_STORAGE_SM = 1
MM_SMS_STORAGE_ME = 2
MM_SMS_STORAGE_MT = 3
MM_SMS_STORAGE_SR = 4
MM_SMS_STORAGE_BM = 5
MM_SMS_STORAGE_TA = 6


# Errors
class MMError(dbus.exceptions.DBusException):
    def __init__(self, errno, *args, **kwargs):
        super(MMError, self).__init__(self, args, kwargs)
        self.include_traceback = False
        self._error_name_base = None
        self._error_name_map = None
        self._Setup()
        self._dbus_error_name = (self._error_name_base +
            self._error_name_map[errno])

    def _Setup(self):
        raise NotImplementedError()


class MMConnectionError(MMError):

    UNKNOWN = 0
    NO_CARRIER = 1
    NO_DIALTONE = 2
    BUSY = 3
    NO_ANSWER = 4

    def _Setup(self):
        self._error_name_base = I_MODEM_MANAGER + '.Connection'
        self._error_name_map = {
            self.UNKNOWN : '.Unknown',
            self.NO_CARRIER : '.NoCarrier',
            self.NO_DIALTONE : '.NoDialtone',
            self.BUSY : '.Busy',
            self.NO_ANSWER : '.NoAnswer'
        }


class MMCoreError(MMError):

    FAILED = 0
    CANCELLED = 1
    ABORTED = 2
    UNSUPPORTED = 3
    NO_PLUGINS = 4
    UNAUTHORIZED = 5
    INVALID_ARGS = 6
    IN_PROGRESS = 7
    WRONG_STATE = 8
    CONNECTED = 9
    TOO_MANY = 10
    NOT_FOUND = 11
    RETRY = 12
    EXISTS = 13

    def _Setup(self):
        self._error_name_base = I_MODEM_MANAGER + '.Core'
        self._error_name_map = {
            self.FAILED : '.Failed',
            self.CANCELLED : '.Cancelled',
            self.ABORTED : '.Aborted',
            self.UNSUPPORTED : '.Unsupported',
            self.NO_PLUGINS : '.NoPlugins',
            self.UNAUTHORIZED : '.Unauthorized',
            self.INVALID_ARGS : '.InvalidArgs',
            self.IN_PROGRESS : '.InProgress',
            self.WRONG_STATE : '.WrongState',
            self.CONNECTED : '.Connected',
            self.TOO_MANY : '.TooMany',
            self.NOT_FOUND : '.NotFound',
            self.RETRY : '.Retry',
            self.EXISTS : '.Exists'
        }


class MMMessageError(MMError):

    ME_FAILURE = 300
    SMS_SERVICE_RESERVED = 301
    NOT_ALLOWED = 302
    NOT_SUPPORTED = 303
    INVALID_PDU_PARAMETER = 304
    INVALID_TEXT_PARAMETER = 305
    SIM_NOT_INSERTED = 310
    SIM_PIN = 311
    PH_SIM_PIN = 312
    SIM_FAILURE = 313
    SIM_BUSY = 314
    SIM_WRONG = 315
    SIM_PUK = 316
    SIM_PIN2 = 317
    SIM_PUK2 = 318
    MEMORY_FAILURE = 320
    INVALID_INDEX = 321
    MEMORY_FULL = 322
    SMSC_ADDRESS_UNKNOWN = 330
    NO_NETWORK = 331
    NETWORK_TIMEOUT = 332
    NO_CNMA_ACK_EXPECTED = 340
    UNKNOWN = 500

    def _Setup(self):
        self._error_name_base = I_MODEM_MANAGER + '.Message'
        self._error_name_map = {
            self.ME_FAILURE : '.MeFailure ',
            self.SMS_SERVICE_RESERVED : '.SmsServiceReserved',
            self.NOT_ALLOWED : '.NotAllowed',
            self.NOT_SUPPORTED : '.NotSupported',
            self.INVALID_PDU_PARAMETER :
                    '.InvalidPduParameter',
            self.INVALID_TEXT_PARAMETER :
                    '.InvalidTextParameter',
            self.SIM_NOT_INSERTED : '.SimNotInserted',
            self.SIM_PIN : '.SimPin',
            self.PH_SIM_PIN : '.PhSimPin',
            self.SIM_FAILURE : '.SimFailure',
            self.SIM_BUSY : '.SimBusy',
            self.SIM_WRONG : '.SimWrong',
            self.SIM_PUK : '.SimPuk',
            self.SIM_PIN2 : '.SimPin2',
            self.SIM_PUK2 : '.SimPuk2',
            self.MEMORY_FAILURE : '.MemoryFailure',
            self.INVALID_INDEX : '.InvalidIndex',
            self.MEMORY_FULL : '.MemoryFull',
            self.SMSC_ADDRESS_UNKNOWN : '.SmscAddressUnknown',
            self.NO_NETWORK : '.NoNetwork',
            self.NETWORK_TIMEOUT : '.NetworkTimeout',
            self.NO_CNMA_ACK_EXPECTED : '.NoCnmaAckExpected',
            self.UNKNOWN : '.Unknown'
        }


class MMMobileEquipmentError(MMError):

    PHONE_FAILURE = 0
    NO_CONNECTION = 1
    LINK_RESERVED = 2
    NOT_ALLOWED = 3
    NOT_SUPPORTED = 4
    PH_SIM_PIN = 5
    PH_FSIM_PIN = 6
    PH_FSIM_PUK = 7
    SIM_NOT_INSERTED = 10
    SIM_PIN = 11
    SIM_PUK = 12
    SIM_FAILURE = 13
    SIM_BUSY = 14
    SIM_WRONG = 15
    INCORRECT_PASSWORD = 16
    SIM_PIN2 = 17
    SIM_PUK2 = 18
    MEMORY_FULL = 20
    INVALID_INDEX = 21
    NOT_FOUND = 22
    MEMORY_FAILURE = 23
    TEXT_TOO_LONG = 24
    INVALID_CHARS = 25
    DIAL_STRING_TOO_LONG = 26
    DIAL_STRING_INVALID = 27
    NO_NETWORK = 30
    NETWORK_TIMEOUT = 31
    NETWORK_NOT_ALLOWED = 32
    NETWORK_PIN = 40
    NETWORK_PUK = 41
    NETWORK_SUBSET_PIN = 42
    NETWORK_SUBSET_PUK = 43
    SERVICE_PIN = 44
    SERVICE_PUK = 45
    CORP_PIN = 46
    CORP_PUK = 47
    UNKNOWN = 100
    # GPRS related errors
    GPRS_ILLEGAL_MS = 103
    GPRS_ILLEGAL_ME = 106
    GPRS_SERVICE_NOT_ALLOWED = 107
    GPRS_PLMN_NOT_ALLOWED = 111
    GPRS_LOCATION_NOT_ALLOWED = 112
    GPRS_ROAMING_NOT_ALLOWED = 113
    GPRS_SERVICE_OPTION_NOT_SUPPORTED = 132
    GPRS_SERVICE_OPTION_NOT_SUBSCRIBED = 133
    GPRS_SERVICE_OPTION_OUT_OF_ORDER = 134
    GPRS_UNKNOWN = 148
    GPRS_PDP_AUTH_FAILURE = 149
    GPRS_INVALID_MOBILE_CLASS = 150

    def _Setup(self):
        self._error_name_base = I_MODEM_MANAGER + '.MobileEquipment'
        self._error_name_map = {
          self.PHONE_FAILURE : '.PhoneFailure',
          self.NO_CONNECTION : '.NoConnection',
          self.LINK_RESERVED : '.LinkReserved',
          self.NOT_ALLOWED : '.NotAllowed',
          self.NOT_SUPPORTED : '.NotSupported',
          self.PH_SIM_PIN : '.PhSimPin',
          self.PH_FSIM_PIN : '.PhFsimPin',
          self.PH_FSIM_PUK : '.PhFsimPuk',
          self.SIM_NOT_INSERTED : '.SimNotInserted',
          self.SIM_PIN : '.SimPin',
          self.SIM_PUK : '.SimPuk',
          self.SIM_FAILURE : '.SimFailure',
          self.SIM_BUSY : '.SimBusy',
          self.SIM_WRONG : '.SimWrong',
          self.INCORRECT_PASSWORD :
              '.IncorrectPassword',
          self.SIM_PIN2 : '.SimPin2',
          self.SIM_PUK2 : '.SimPuk2',
          self.MEMORY_FULL : '.MemoryFull',
          self.INVALID_INDEX : '.InvalidIndex',
          self.NOT_FOUND : '.NotFound',
          self.MEMORY_FAILURE : '.MemoryFailure',
          self.TEXT_TOO_LONG : '.TextTooLong',
          self.INVALID_CHARS : '.InvalidChars',
          self.DIAL_STRING_TOO_LONG :
              '.DialStringTooLong',
          self.DIAL_STRING_INVALID :
              '.DialStringInvalid',
          self.NO_NETWORK : '.NoNetwork',
          self.NETWORK_TIMEOUT : '.NetworkTimeout',
          self.NETWORK_NOT_ALLOWED :
              '.NetworkNotAllowed',
          self.NETWORK_PIN : '.NetworkPin',
          self.NETWORK_PUK : '.NetworkPuk',
          self.NETWORK_SUBSET_PIN :
              '.NetworkSubsetPin',
          self.NETWORK_SUBSET_PUK :
              '.NetworkSubsetPuk',
          self.SERVICE_PIN : '.ServicePin',
          self.SERVICE_PUK : '.ServicePuk',
          self.CORP_PIN : '.CorpPin',
          self.CORP_PUK : '.CorpPuk',
          self.UNKNOWN : '.Unknown',
          self.GPRS_ILLEGAL_MS : '.Gprs.IllegalMs',
          self.GPRS_ILLEGAL_ME : '.Gprs.IllegalMe',
          self.GPRS_SERVICE_NOT_ALLOWED :
              '.Gprs.ServiceNotAllowed',
          self.GPRS_PLMN_NOT_ALLOWED :
              '.Gprs.PlmnNotAllowed',
          self.GPRS_LOCATION_NOT_ALLOWED :
              '.Gprs.LocationNotAllowed',
          self.GPRS_ROAMING_NOT_ALLOWED :
              '.Gprs.RoamingNotAllowed',
          self.GPRS_SERVICE_OPTION_NOT_SUPPORTED :
              '.Gprs.ServiceOptionNotSupported',
          self.GPRS_SERVICE_OPTION_NOT_SUBSCRIBED :
              '.Gprs.ServiceOptionNotSubscribed',
          self.GPRS_SERVICE_OPTION_OUT_OF_ORDER :
              '.Gprs.ServiceOptionOutOfOrder',
          self.GPRS_UNKNOWN :
              '.Gprs.Unknown',
          self.GPRS_PDP_AUTH_FAILURE :
              '.Gprs.PdpAuthFailure',
          self.GPRS_INVALID_MOBILE_CLASS :
              '.Gprs.InvalidMobileClass'
        }


class MMSerialError(MMError):

    UNKNOWN = 0
    OPEN_FAILED = 1
    SEND_FAILED = 2
    RESPONSE_TIMEOUT = 3
    OPEN_FAILED_NO_DEVICE = 4
    FLASH_FAILED = 5
    NOT_OPEN = 6

    def _Setup(self):
        self._error_name_base = I_MODEM_MANAGER + '.Serial'
        self._error_name_map = {
            self.UNKNOWN : '.Unknown',
            self.OPEN_FAILED : '.OpenFailed',
            self.SEND_FAILED : '.SendFailed',
            self.RESPONSE_TIMEOUT : '.ResponseTimeout',
            self.OPEN_FAILED_NO_DEVICE : '.OpenFailedNoDevice',
            self.FLASH_FAILED : '.FlashFailed',
            self.NOT_OPEN : '.NotOpen'
        }


class MMCdmaActivationError(MMError):

    NONE = 0
    UNKNOWN = 1
    ROAMING = 2
    WRONG_RADIO_INTERFACE = 3
    COULD_NOT_CONNECT = 4
    SECURITY_AUTHENTICATION_FAILED = 5
    PROVISIONING_FAILED = 6
    NO_SIGNAL = 7
    TIMED_OUT = 8
    START_FAILED = 9

    def _Setup(self):
        self._error_name_base = I_MODEM_MANAGER + '.CdmaActivation'
        self._error_name_map = {
            self.NONE : '.None',
            self.UNKNOWN :
                '.Unknown',
            self.ROAMING :
                '.Roaming',
            self.WRONG_RADIO_INTERFACE :
                '.WrongRadioInterface',
            self.COULD_NOT_CONNECT :
                '.CouldNotConnect',
            self.SECURITY_AUTHENTICATION_FAILED :
                '.SecurityAuthenticationFailed',
            self.PROVISIONING_FAILED :
                '.ProvisioningFailed',
            self.NO_SIGNAL :
                '.NoSignal',
            self.TIMED_OUT :
                '.TimedOut',
            self.START_FAILED :
                '.StartFailed'
        }
