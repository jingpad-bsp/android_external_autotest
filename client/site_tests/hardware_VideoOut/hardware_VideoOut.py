# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os.path

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error, site_ui

class hardware_VideoOut(test.test):
    version = 1
    XRANDR_PATH = "/usr/bin/xrandr"
    RECONFIG_PATH = "/usr/sbin/monitor_reconfigure"
    HDMI_ID = "HDMI"
    VGA_ID = "VGA"
    
    
    # Returns True if given |output| port is found on system.
    def __query_for_output(self, output):
        query_cmd = "%s -q | grep %s -c" % (self.XRANDR_PATH, output)
        xrandr_out = utils.system_output(site_ui.xcommand(query_cmd), 
                                         ignore_status=True)        
        return int(xrandr_out) > 0
    
    
    # Returns True if given |output| port has a connected device.
    def __output_connected(self, output):
        query_cmd = "%s -q | grep '%s[0-9] connected' -c" % \
            (self.XRANDR_PATH, output)
        xrandr_out = utils.system_output(site_ui.xcommand(query_cmd), 
                                         ignore_status=True)
        return int(xrandr_out) > 0
    
    
    # Returns if given |output| port has a device that has been configured
    # otherwise raises TestFail
    def __output_is_set(self, output):
        query_cmd = "%s -q | grep '%s[0-9] connected' -n" % \
            (self.XRANDR_PATH, output)
        start_line = int(
            utils.system_output(site_ui.xcommand(query_cmd)).split(':')[0]
        )
        
        # Gets 100 lines (to be safe) after context to get output after 
        query_cmd = \
            "%s -q | grep '%s[0-9] connected' -n -A 100 | grep connected" % \
                (self.XRANDR_PATH, output)
            
        try:
            end_line = int(utils.system_output(
                site_ui.xcommand(query_cmd)).split('\n')[1].split('-')[0])
        except:
            logging.info("End line not found, assuming last output")
            end_line = -1
        
        if end_line != -1:
            lines_between = end_line - start_line - 1            
        else:
            line_between = 100
        query_cmd = "%s -q | grep '%s[0-9] connected' -A %d | grep \\*" % \
                (self.XRANDR_PATH, output, lines_between)
        try:
            utils.system(site_ui.xcommand(query_cmd))
        except:
            raise error.TestFail("%s not set with monitor_reconfigure" % output)
    
    
    # Configures |output| and returns if |output| has been configured
    def __configure_and_check_output(self, output):        
        connected = self.__output_connected(output)
        if not connected:
            logging.warning(
                "%s port detected but no connected device" % output
                )            
        else:            
            #TODO(sosa@chromium.org) - Verify this is synchronous.
            utils.system(site_ui.xcommand(self.RECONFIG_PATH))
            self.__output_is_set(output)

            
    def run_once(self):
        # Sanity check for xrandr application.
        if not os.path.isfile(self.XRANDR_PATH):
            raise error.TestFail("""
                XRandr missing from device cannot complete test        
            """)
            
        # Determine if devices of interest are on system.                
        hdmi_exists = self.__query_for_output(self.HDMI_ID)
        vga_exists = self.__query_for_output(self.VGA_ID)
        
        # Raises NAError since these are optional devices.
        if (not hdmi_exists) and (not vga_exists):
            raise error.TestNAError("Neither VGA or HDMI ports detected")
        
        # Sanity check to make sure we can configure the devices.
        if not os.path.isfile(self.RECONFIG_PATH):
            raise error.TestFail("""
                Device detected but missing monitor_reconfigure tool
            """)       
                                             
        # If devices exist, we should be able to configure and enable them
        if hdmi_exists:
            self.__configure_and_check_output(self.HDMI_ID)
        if vga_exists:
            self.__configure_and_check_output(self.VGA_ID)        