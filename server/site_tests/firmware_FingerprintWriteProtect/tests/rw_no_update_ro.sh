#!/bin/bash

# This test expects HW write protect to be enabled when run (wp_gpio_asserted)
echo "Running test to verify that RW cannot update RO"

FW_FILE="$1"

# make sure file exists
if [[ ! -f "${FW_FILE}" ]]; then
  echo "Cannot find firmware file: ${FW_FILE}"
  exit 1
fi

# Make sure software write protect is enabled
# TODO(b/116396469): These commands currently return an error even though
# they succeed
ectool --name=cros_fp flashprotect enable || true
sleep 2
ectool --name=cros_fp reboot_ec || true
sleep 2

EXPECTED_FLASHPROTECT_OUTPUT="$(cat <<SETVAR
Flash protect flags: 0x0000000b wp_gpio_asserted ro_at_boot ro_now
Valid flags:         0x0000003f wp_gpio_asserted ro_at_boot ro_now all_now STUCK INCONSISTENT
Writable flags:      0x00000004 all_now
SETVAR
)"
FLASHPROTECT_OUTPUT="$(ectool --name=cros_fp flashprotect)"

if [[ "${FLASHPROTECT_OUTPUT}" != "${EXPECTED_FLASHPROTECT_OUTPUT}" ]]; then
  echo "Incorrect flashprotect state: ${FLASHPROTECT_OUTPUT}"
  echo "Make sure HW write protect is enabled (wp_gpio_asserted)"
  exit 1
fi

# Try to flash the RO firmware (expected to fail)
flashrom --fast-verify -V -p ec:type=fp -i EC_RO -w "${FW_FILE}"
if [[ $? -eq 0 ]]; then
  echo "Expected flashing of read-only firmware to fail"
  exit 1
fi
