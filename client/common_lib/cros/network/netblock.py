# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class Netblock(object):
    """Utility class for transforming netblock address to related strings."""

    @staticmethod
    def _octets_to_addr(octets):
        """Transform a list of bytes into a string IP address.

        @param octets list of ints (e.g. [192.168.0.1]).
        @return string IP address (e.g. '192.168.0.1.').

        """
        return '.'.join(map(str, octets))


    @staticmethod
    def _int_to_octets(num):
        """Tranform a 32 bit number into a list of 4 octets.

        @param num: number to convert to octets.
        @return list of int values <= 8 bits long.

        """
        return [(num >> s) & 0xff for s in (24, 16, 8, 0)]


    @staticmethod
    def from_addr(addr, prefix_len=32):
        """Construct a netblock address from a normal IP address.

        @param addr: string IP address (e.g. '192.168.0.1').
        @param prefix_len int length of IP address prefix.
        @return Netblock object.

        """
        return Netblock('/'.join([addr, str(prefix_len)]))


    @property
    def netblock(self):
        """@return the IPv4 address/prefix, e.g., '192.168.0.1/24'."""
        return '/'.join([self._octets_to_addr(self._octets),
                         str(self.prefix_len)])


    @property
    def netmask(self):
        """@return the IPv4 netmask, e.g., '255.255.255.0'."""
        return self._octets_to_addr(self._mask_octets)


    @property
    def prefix_len(self):
        """@return the IPv4 prefix len, e.g., 24."""
        return self._prefix_len


    @property
    def subnet(self):
        """@return the IPv4 subnet, e.g., '192.168.0.0'."""
        octets = [a & m for a, m in zip(self._octets, self._mask_octets)]
        return self._octets_to_addr(octets)


    @property
    def broadcast(self):
        """@return the IPv4 broadcast address, e.g., '192.168.0.255'."""
        octets = [a | (m ^ 0xff)
                  for a, m in zip(self._octets, self._mask_octets)]
        return self._octets_to_addr(octets)


    @property
    def addr(self):
        """@return the IPv4 address, e.g., '192.168.0.1'."""
        return self._octets_to_addr(self._octets)


    def __init__(self, netblock_str):
        addr_str, bits_str = netblock_str.split('/')
        self._octets = map(int, addr_str.split('.'))
        bits = int(bits_str)
        mask_bits = (-1 << (32 - bits)) & 0xffffffff
        self._mask_octets = self._int_to_octets(mask_bits)
        self._prefix_len = bits


    def get_addr_in_block(self, offset):
        """Get an address in a subnet.

        For instance if this netblock represents 192.168.0.1/24,
        then get_addr_in_block(5) would return 192.168.0.5.

        @param offset int offset in block, (e.g. 5).
        @return string address (e.g. '192.168.0.5').

        """
        offset = self._int_to_octets(offset)
        octets = [(a & m) + o
                  for a, m, o in zip(self._octets, self._mask_octets, offset)]
        return self._octets_to_addr(octets)
