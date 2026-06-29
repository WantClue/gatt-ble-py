#!/usr/bin/env python3
"""Scan for the BitForge setup BLE device, then read out every characteristic.

Linux uses BlueZ, which (unlike iOS) does not cache GATT/device names, so this
shows the live, ground-truth values straight off the device.

Usage:
    python3 ble_read.py                 # auto-find a device named "BitForge-*"
    python3 ble_read.py --name BitForge-A071
    python3 ble_read.py --address AA:BB:CC:DD:EE:FF
    python3 ble_read.py --write status   # also demo: read the 'status' char

Requires: pip install bleak
"""

import argparse
import asyncio
import sys

from bleak import BleakClient, BleakScanner

SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b"

# UUID -> friendly name (derived from the firmware's BLE_UUID128_INIT arrays)
KNOWN = {
    SERVICE_UUID: "setup service",
    "beb5483e-36e1-4688-b7f5-ea07361b26a8": "wifi_ssid",
    "beb5483e-36e1-4688-b7f5-ea07361b26a9": "wifi_password",
    "beb5483e-36e1-4688-b7f5-ea07361b26aa": "pool_url",
    "beb5483e-36e1-4688-b7f5-ea07361b26ab": "pool_port",
    "beb5483e-36e1-4688-b7f5-ea07361b26ac": "pool_user",
    "beb5483e-36e1-4688-b7f5-ea07361b26ad": "pool_password",
    "beb5483e-36e1-4688-b7f5-ea07361b26ae": "status",
    "beb5483e-36e1-4688-b7f5-ea07361b26af": "command",
    # Standard GATT
    "00002a00-0000-1000-8000-00805f9b34fb": "GAP Device Name (0x2A00)",
    "00002a01-0000-1000-8000-00805f9b34fb": "GAP Appearance (0x2A01)",
}


def label(uuid: str) -> str:
    return KNOWN.get(uuid.lower(), "")


def decode(data: bytes) -> str:
    try:
        return repr(data.decode("utf-8"))
    except UnicodeDecodeError:
        return data.hex(" ")


async def find_device(name: str | None, address: str | None):
    if address:
        print(f"Looking for {address} ...")
        return await BleakScanner.find_device_by_address(address, timeout=15.0)

    print("Scanning 10s for the setup device ...")
    devices = await BleakScanner.discover(timeout=10.0, return_adv=True)
    prefix = (name or "BitForge").lower()
    for dev, adv in devices.values():
        local = (adv.local_name or dev.name or "")
        uuids = [u.lower() for u in (adv.service_uuids or [])]
        if local.lower().startswith(prefix) or SERVICE_UUID in uuids:
            print(f"Found: {local or '(no name)'}  [{dev.address}]  rssi={adv.rssi}")
            return dev
    return None


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", help="device name prefix to match (default: BitForge)")
    ap.add_argument("--address", help="connect directly to this BLE MAC")
    args = ap.parse_args()

    dev = await find_device(args.name, args.address)
    if dev is None:
        print("No matching device found. Is it advertising / already connected elsewhere?")
        return 1

    async with BleakClient(dev) as client:
        print(f"\nConnected to {dev.address}\n" + "=" * 60)
        for service in client.services:
            tag = label(service.uuid)
            print(f"\nService {service.uuid}  {('<' + tag + '>') if tag else ''}")
            for ch in service.characteristics:
                tag = label(ch.uuid)
                head = f"  {ch.uuid}  {('<' + tag + '>') if tag else ''}  [{','.join(ch.properties)}]"
                if "read" in ch.properties:
                    try:
                        val = await client.read_gatt_char(ch.uuid)
                        print(f"{head}\n      = {decode(val)}")
                    except Exception as e:  # noqa: BLE001
                        print(f"{head}\n      (read failed: {e})")
                else:
                    print(head)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        pass
