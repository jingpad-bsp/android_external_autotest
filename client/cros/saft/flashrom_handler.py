#!/usr/bin/python
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A module to support automated testing of ChromeOS firmware.

Utilizes services provided by saft_flashrom_util.py read/write the
flashrom chip and to parse the flash rom image.

See docstring for FlashromHandler class below.
"""

import hashlib
import os
import struct
import tempfile

class FvSection(object):
    """An object to hold information about a firmware section.

    This includes file names for the signature header and the body, and the
    version number.
    """

    def __init__(self, sig_name, body_name):
        self._sig_name = sig_name
        self._body_name = body_name
        self._version = -1  # Is not set on construction.
        self._flags = 0  # Is not set on construction.
        self._sha = None  # Is not set on construction.
        self._sig_sha = None # Is not set on construction.
        self._datakey_version = -1 # Is not set on construction.
        self._kernel_subkey_version = -1 # Is not set on construction.

    def names(self):
        return (self._sig_name, self._body_name)

    def get_sig_name(self):
        return self._sig_name

    def get_body_name(self):
        return self._body_name

    def get_version(self):
        return self._version

    def get_flags(self):
        return self._flags

    def get_sha(self):
        return self._sha

    def get_sig_sha(self):
        return self._sig_sha

    def get_datakey_version(self):
        return self._datakey_version

    def get_kernel_subkey_version(self):
        return self._kernel_subkey_version

    def set_version(self, version):
        self._version = version

    def set_flags(self, flags):
        self._flags = flags

    def set_sha(self, sha):
        self._sha = sha

    def set_sig_sha(self, sha):
        self._sig_sha = sha

    def set_datakey_version(self, version):
        self._datakey_version = version

    def set_kernel_subkey_version(self, version):
        self._kernel_subkey_version = version

class FlashromHandlerError(Exception):
    pass


class FlashromHandler(object):
    """An object to provide logical services for automated flashrom testing."""

    DELTA = 1  # value to add to a byte to corrupt a section contents

    # File in the state directory to store public root key.
    PUB_KEY_FILE_NAME = 'root.pubkey'
    FW_KEYBLOCK_FILE_NAME = 'firmware.keyblock'
    FW_PRIV_DATA_KEY_FILE_NAME = 'firmware_data_key.vbprivk'
    KERNEL_SUBKEY_FILE_NAME = 'kernel_subkey.vbpubk'

    def __init__(self):
    # make sure it does not accidentally overwrite the image.
        self.fum = None
        self.chros_if = None
        self.image = ''
        self.pub_key_file = ''

    def init(self, flashrom_util_module,
             chros_if,
             pub_key_file=None,
             dev_key_path='./',
             target='bios'):
        """Flashrom handler initializer.

        Args:
          flashrom_util_module - a module providing flashrom access utilities.
          chros_if - a module providing interface to Chromium OS services
          pub_key_file - a string, name of the file contaning a public key to
                         use for verifying both existing and new firmware.
        """
        if target == 'bios':
            self.fum = flashrom_util_module.flashrom_util(target_is_ec=False)
            self.fv_sections = {
                'a': FvSection('VBOOTA', 'FVMAIN'),
                'b': FvSection('VBOOTB', 'FVMAINB'),
                }
        elif target == 'ec':
            self.fum = flashrom_util_module.flashrom_util(target_is_ec=True)
            self.fv_sections = {
                'rw': FvSection(None, 'EC_RW'),
                }
        else:
            raise FlashromHandlerError("Invalid target.")
        self.chros_if = chros_if
        self.pub_key_file = pub_key_file
        self.dev_key_path = dev_key_path

    def new_image(self, image_file=None):
        """Parse the full flashrom image and store sections into files.

        Args:
          image_file - a string, the name of the file contaning full ChromeOS
                       flashrom image. If not passed in or empty - the actual
                       flashrom is read and its contents are saved into a
                       temporary file which is used instead.

        The input file is parsed and the sections of importance (as defined in
        self.fv_sections) are saved in separate files in the state directory
        as defined in the chros_if object.
        """

        if image_file:
            self.image = open(image_file, 'rb').read()
            self.fum.set_firmware_layout(image_file)
        else:
            self.image = self.fum.read_whole()

        for section in self.fv_sections.itervalues():
            for subsection_name in section.names():
                if not subsection_name:
                    continue
                f = open(self.chros_if.state_dir_file(subsection_name), 'wb')
                f.write(self.fum.get_section(self.image, subsection_name))
                f.close()

            s = hashlib.sha1()
            s.update(self.fum.get_section(self.image, section.get_body_name()))
            section.set_sha(s.hexdigest())

            # If there is no "sig" subsection, skip reading version and flags.
            if not section.get_sig_name():
                continue

            # Now determine this section's version number.
            vb_section = self.fum.get_section(
                self.image, section.get_sig_name())

            section.set_version(self.chros_if.retrieve_body_version(vb_section))
            section.set_flags(self.chros_if.retrieve_preamble_flags(vb_section))
            section.set_datakey_version(
                self.chros_if.retrieve_datakey_version(vb_section))
            section.set_kernel_subkey_version(
                self.chros_if.retrieve_kernel_subkey_version(vb_section))

            s = hashlib.sha1()
            s.update(self.fum.get_section(self.image, section.get_sig_name()))
            section.set_sig_sha(s.hexdigest())

        if not self.pub_key_file:
            self._retrieve_pub_key()

    def _retrieve_pub_key(self):
        """Retrieve root public key from the firmware GBB section."""

        gbb_header_format = '<4s20s2I'
        pubk_header_format = '<2Q'

        gbb_section = self.fum.get_section(self.image, 'FV_GBB')

        # do some sanity checks
        try:
            sig, _, rootk_offs, rootk_size = struct.unpack_from(
                gbb_header_format, gbb_section)
        except struct.error, e:
            raise FlashromHandlerError(e)

        if sig != '$GBB' or (rootk_offs + rootk_size) > len(gbb_section):
            raise FlashromHandlerError('Bad gbb header')

        key_body_offset, key_body_size = struct.unpack_from(
            pubk_header_format, gbb_section, rootk_offs)

        # Generally speaking the offset field can be anything, but in case of
        # GBB section the key is stored as a standalone entity, so the offset
        # of the key body is expected to be equal to the key header size of
        # 0x20.
        # Should this convention change, the check below would fail, which
        # would be a good prompt for revisiting this test's behavior and
        # algorithms.
        if key_body_offset != 0x20 or key_body_size > rootk_size:
            raise FlashromHandlerError('Bad public key format')

        # All checks passed, let's store the key in a file.
        self.pub_key_file = self.chros_if.state_dir_file(self.PUB_KEY_FILE_NAME)
        keyf = open(self.pub_key_file, 'w')
        key = gbb_section[
            rootk_offs:rootk_offs + key_body_offset + key_body_size]
        keyf.write(key)
        keyf.close()

    def verify_image(self):
        """Confirm the image's validity.

        Using the file supplied to init() as the public key container verify
        the two sections' (FirmwareA and FirmwareB) integrity. The contents of
        the sections is taken from the files created by new_image()

        In case there is an integrity error raises FlashromHandlerError
        exception with the appropriate error message text.
        """

        for section in self.fv_sections.itervalues():
            cmd = 'vbutil_firmware --verify %s --signpubkey %s  --fv %s' % (
                self.chros_if.state_dir_file(section.get_sig_name()),
                self.pub_key_file,
                self.chros_if.state_dir_file(section.get_body_name()))
            self.chros_if.run_shell_command(cmd)

    def _modify_section(self, section, delta, body_or_sig=False,
                        corrupt_all=False):
        """Modify a firmware section inside the image, either body or signature.

        If corrupt_all is set, the passed in delta is added to all bytes in the
        section. Otherwise, the delta is added to the value located at 2% offset
        into the section blob, either body or signature.

        Calling this function again for the same section the complimentary
        delta value would restore the section contents.
        """

        if not self.image:
            raise FlashromHandlerError(
                'Attempt at using an uninitialized object')
        if section not in self.fv_sections:
            raise FlashromHandlerError('Unknown FW section %s'
                                       % section)

        # Get the appropriate section of the image.
        if body_or_sig:
            subsection_name = self.fv_sections[section].get_body_name()
        else:
            subsection_name = self.fv_sections[section].get_sig_name()
        blob = self.fum.get_section(self.image, subsection_name)

        # Modify the byte in it within 2% of the section blob.
        modified_index = len(blob) / 50
        if corrupt_all:
            blob_list = [('%c' % ((ord(x) + delta) % 0x100)) for x in blob]
        else:
            blob_list = list(blob)
            blob_list[modified_index] = ('%c' %
                    ((ord(blob[modified_index]) + delta) % 0x100))
        self.image = self.fum.put_section(self.image,
                                          subsection_name, ''.join(blob_list))

        return subsection_name

    def corrupt_section(self, section, corrupt_all=False):
        """Corrupt a section signature of the image"""

        return self._modify_section(section, self.DELTA, body_or_sig=False,
                                    corrupt_all=corrupt_all)

    def corrupt_section_body(self, section, corrupt_all=False):
        """Corrupt a section body of the image"""

        return self._modify_section(section, self.DELTA, body_or_sig=True,
                                    corrupt_all=corrupt_all)

    def restore_section(self, section, restore_all=False):
        """Restore a previously corrupted section signature of the image."""

        return self._modify_section(section, -self.DELTA, body_or_sig=False,
                                    corrupt_all=restore_all)

    def restore_section_body(self, section, restore_all=False):
        """Restore a previously corrupted section body of the image."""

        return self._modify_section(section, -self.DELTA, body_or_sig=True,
                                    corrupt_all=restore_all)

    def corrupt_firmware(self, section, corrupt_all=False):
        """Corrupt a section signature in the FLASHROM!!!"""

        subsection_name = self.corrupt_section(section, corrupt_all=corrupt_all)
        self.fum.write_partial(self.image, (subsection_name, ))

    def corrupt_firmware_body(self, section, corrupt_all=False):
        """Corrupt a section body in the FLASHROM!!!"""

        subsection_name = self.corrupt_section_body(section,
                                                    corrupt_all=corrupt_all)
        self.fum.write_partial(self.image, (subsection_name, ))

    def restore_firmware(self, section, restore_all=False):
        """Restore the previously corrupted section sig in the FLASHROM!!!"""

        subsection_name = self.restore_section(section, restore_all=restore_all)
        self.fum.write_partial(self.image, (subsection_name, ))

    def restore_firmware_body(self, section, restore_all=False):
        """Restore the previously corrupted section body in the FLASHROM!!!"""

        subsection_name = self.restore_section_body(section,
                                                    restore_all=False)
        self.fum.write_partial(self.image, (subsection_name, ))

    def firmware_sections_equal(self):
        """Check if firmware sections A and B are equal.

        This function presumes that the entire BIOS image integrity has been
        verified, so different signature sections mean different images and
        vice versa.
        """
        sig_a = self.fum.get_section(self.image,
                                      self.fv_sections['a'].get_sig_name())
        sig_b = self.fum.get_section(self.image,
                                      self.fv_sections['b'].get_sig_name())
        return sig_a == sig_b

    def copy_from_to(self, src, dst):
        """Copy one firmware image section to another.

        This function copies both signature and body of one firmware section
        into another. After this function runs both sections are identical.
        """
        src_sect = self.fv_sections[src]
        dst_sect = self.fv_sections[dst]
        self.image = self.fum.put_section(
            self.image,
            dst_sect.get_body_name(),
            self.fum.get_section(self.image, src_sect.get_body_name()))
        self.image = self.fum.put_section(
            self.image,
            dst_sect.get_sig_name(),
            self.fum.get_section(self.image, src_sect.get_sig_name()))

    def write_whole(self):
        """Write the whole image into the flashrom."""

        if not self.image:
            raise FlashromHandlerError(
                'Attempt at using an uninitialized object')
        self.fum.write_whole(self.image)

    def dump_whole(self, filename):
        """Write the whole image into a file."""

        if not self.image:
            raise FlashromHandlerError(
                'Attempt at using an uninitialized object')
        open(filename, 'w').write(self.image)

    def dump_partial(self, subsection_name, filename):
        """Write the subsection part into a file."""

        if not self.image:
            raise FlashromHandlerError(
                'Attempt at using an uninitialized object')
        blob = self.fum.get_section(self.image, subsection_name)
        open(filename, 'w').write(blob)

    def get_gbb_flags(self):
        """Retrieve the GBB flags"""
        gbb_header_format = '<12sL'
        gbb_section = self.fum.get_section(self.image, 'FV_GBB')
        try:
            _, gbb_flags = struct.unpack_from(gbb_header_format, gbb_section)
        except struct.error, e:
            raise FlashromHandlerError(e)
        return gbb_flags

    def enable_write_protect(self):
        """Enable write protect of the flash chip"""
        self.fum.enable_write_protect()

    def disable_write_protect(self):
        """Disable write protect of the flash chip"""
        self.fum.disable_write_protect()

    def get_section_sig_sha(self, section):
        """Retrieve SHA1 hash of a firmware vblock section"""
        return self.fv_sections[section].get_sig_sha()

    def get_section_sha(self, section):
        """Retrieve SHA1 hash of a firmware body section"""
        return self.fv_sections[section].get_sha()

    def get_section_version(self, section):
        """Retrieve version number of a firmware section"""
        return self.fv_sections[section].get_version()

    def get_section_flags(self, section):
        """Retrieve preamble flags of a firmware section"""
        return self.fv_sections[section].get_flags()

    def get_section_datakey_version(self, section):
        """Retrieve data key version number of a firmware section"""
        return self.fv_sections[section].get_datakey_version()

    def get_section_kernel_subkey_version(self, section):
        """Retrieve kernel subkey version number of a firmware section"""
        return self.fv_sections[section].get_kernel_subkey_version()

    def get_section_body(self, section):
        """Retrieve body of a firmware section"""
        subsection_name = self.fv_sections[section].get_body_name()
        blob = self.fum.get_section(self.image, subsection_name)
        return blob

    def get_section_sig(self, section):
        """Retrieve vblock of a firmware section"""
        subsection_name = self.fv_sections[section].get_sig_name()
        blob = self.fum.get_section(self.image, subsection_name)
        return blob

    def _find_dtb_offset(self, blob):
        """Return the offset of DTB blob from the given firmware blob"""
        # The RW firmware is concatenated from u-boot, dtb, and ecbin.
        # Search the magic of dtb to locate the dtb bloc.
        return blob.find("\xD0\x0D\xFE\xED\x00")

    def _find_ecbin_offset(self, blob):
        """Return the offset of EC binary from the given firmware blob"""
        dtb_offset = self._find_dtb_offset(blob)
        # If the device tree was found, use it. Otherwise assume an index
        # structure.
        if dtb_offset != -1:
            # The dtb size is a 32-bit integer which follows the magic.
            _, dtb_size = struct.unpack_from(">2L", blob, dtb_offset)
            # The ecbin part is aligned to 4-byte.
            return (dtb_offset + dtb_size + 3) & ~3
        else:
            # The index will have a count, an offset and size for the system
            # firmware, and then an offset and size for the EC binary.
            return struct.unpack_from("<I", blob, 3 * 4)[0]

    def _find_ecbin_size_offset_on_dtb(self, blob):
        """Return the offset of EC binary size on the DTB blob"""
        # We now temporarily use this hack to find the offset.
        # TODO(waihong@chromium.org): Should use fdtget to get the field and
        # fdtput to change it.
        dtb_offset = self._find_dtb_offset(blob)
        # If the device tree wasn't found, give up and return an error.
        if dtb_offset == -1:
            return -1
        # Search the patterns "blob boot,dtb,ecbin" / "blob boot,dtb-rwa,ecbin".
        prop_offset = blob.index("blob boot,dtb", dtb_offset) + 0x18
        ecbin_size_offset = blob.index("ecbin", prop_offset) + 0x18
        return ecbin_size_offset

    def get_section_ecbin(self, section):
        """Retrieve EC binary of a firmware section"""
        blob = self.get_section_body(section)
        ecbin_offset = self._find_ecbin_offset(blob)
        # Remove the pads of ecbin.
        pad = blob[-1]
        ecbin = blob[ecbin_offset :].rstrip(pad)
        return ecbin

    def set_section_body(self, section, blob, write_through=False):
        """Put the supplied blob to the body of the firmware section"""
        subsection_name = self.fv_sections[section].get_body_name()
        self.image = self.fum.put_section(self.image, subsection_name, blob)

        if write_through:
            self.dump_partial(subsection_name,
                              self.chros_if.state_dir_file(subsection_name))
            self.fum.write_partial(self.image, (subsection_name, ))

    def set_section_sig(self, section, blob, write_through=False):
        """Put the supplied blob to the vblock of the firmware section"""
        subsection_name = self.fv_sections[section].get_sig_name()
        self.image = self.fum.put_section(self.image, subsection_name, blob)

        if write_through:
            self.dump_partial(subsection_name,
                              self.chros_if.state_dir_file(subsection_name))
            self.fum.write_partial(self.image, (subsection_name, ))

    def set_section_ecbin(self, section, ecbin, write_through=False):
        """Put the supplied EC binary to the firwmare section.

        Note that the updated firmware image is not signed yet. Should call
        set_section_version() afterward.
        """
        # Remove unncessary padding bytes.
        pad = '\xff'
        align = 4
        ecbin = ecbin.rstrip(pad)
        ecbin += pad * (-len(ecbin) % align)
        ecbin_size = len(ecbin)

        # Put the ecbin into the firmware body.
        old_blob = self.get_section_body(section)
        ecbin_offset = self._find_ecbin_offset(old_blob)
        pad = old_blob[-1]
        pad_size = len(old_blob) - ecbin_offset - ecbin_size

        # Update the size of the EC binary on the DTB.
        dtb_offset = self._find_dtb_offset(old_blob)
        dtb_blob = old_blob[dtb_offset : ecbin_offset]
        dtb_size = ecbin_offset - dtb_offset
        with tempfile.NamedTemporaryFile() as dtb_file:
            dtb_file.write(dtb_blob)
            dtb_file.flush()
            cmd = ["fdtput", "-t lu", dtb_file.name,
                    "/flash/rw-a-boot/ecbin",
                    "reg", str(ecbin_offset), str(ecbin_size)]
            self.chros_if.run_shell_command(' '.join(cmd))

            dtb_file.seek(0)
            dtb_blob = dtb_file.read()
            dtb_blob += pad * (-len(dtb_blob) % align)
            assert len(dtb_blob) == dtb_size, (
                    'Updating DTB should not change its size.')

        # Update the new DTB.
        new_blob = old_blob[0 : dtb_offset] + dtb_blob + ecbin + pad * pad_size

        # Also modify the EC binary size in the new format.
        size_offset = self._find_ecbin_size_offset_on_dtb(new_blob)
        if size_offset == -1:
            # The index will have a count, an offset and size for the system
            # firmware, and then an offset and size for the EC binary.
            new_blob = (new_blob[0 : 4 * 4] + struct.pack('<I', ecbin_size) +
                        new_blob[5 * 4 :])

        self.set_section_body(section, new_blob)
        if write_through:
            subsection_name = self.fv_sections[section].get_body_name()
            self.dump_partial(subsection_name,
                              self.chros_if.state_dir_file(subsection_name))
            self.fum.write_partial(self.image, (subsection_name, ))

    def set_section_version(self, section, version, flags,
                            write_through=False):
        """
        Re-sign the firmware section using the supplied version number and
        flag.
        """
        if (self.get_section_version(section) == version and
            self.get_section_flags(section) == flags):
            return  # No version or flag change, nothing to do.
        if version < 0:
            raise FlashromHandlerError(
                'Attempt to set version %d on section %s' % (version, section))
        fv_section = self.fv_sections[section]
        sig_name = self.chros_if.state_dir_file(fv_section.get_sig_name())
        sig_size = os.path.getsize(sig_name)

        # Construct the command line
        args = ['--vblock %s' % sig_name]
        args.append('--keyblock %s' % os.path.join(
                self.dev_key_path, self.FW_KEYBLOCK_FILE_NAME))
        args.append('--fv %s' % self.chros_if.state_dir_file(
                fv_section.get_body_name()))
        args.append('--version %d' % version)
        args.append('--kernelkey %s' % os.path.join(
                self.dev_key_path, self.KERNEL_SUBKEY_FILE_NAME))
        args.append('--signprivate %s' % os.path.join(
                self.dev_key_path, self.FW_PRIV_DATA_KEY_FILE_NAME))
        args.append('--flags %d' % flags)
        cmd = 'vbutil_firmware %s' % ' '.join(args)
        self.chros_if.run_shell_command(cmd)

        #  Pad the new signature.
        new_sig = open(sig_name, 'a')
        pad = ('%c' % 0) * (sig_size - os.path.getsize(sig_name))
        new_sig.write(pad)
        new_sig.close()

        # Inject the new signature block into the image
        new_sig = open(sig_name, 'r').read()
        self.image = self.fum.put_section(
            self.image, fv_section.get_sig_name(), new_sig)
        if write_through:
            self.fum.write_partial(self.image, (fv_section.get_sig_name(), ))
