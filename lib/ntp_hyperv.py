
# Copyright (c) 2017-2018 Canonical Ltd
# License: GPLv3
# Author: Paul Gear

import os
import sys

"""Hyper-V host clock sync handling for NTP charm

References:
- https://bugs.launchpad.net/bugs/1676635
- https://patchwork.kernel.org/patch/9525945/
- https://social.msdn.microsoft.com/Forums/en-US/8c0a1026-0b02-405a-848e-628e68229eaf/
"""

_device_class = '9527e630-d0ae-497b-adce-e80ab0175caf'
_vmbus_dir = '/sys/bus/vmbus/'


def log(msg):
    print(msg, file=sys.stderr)


def _find_host_sync_device():
    """Search for a vmbus device directory whose class matches _device_class"""
    try:
        for d in os.listdir(os.path.join(_vmbus_dir, 'devices')):
            try:
                f = open(os.path.join(_vmbus_dir, 'devices', d, 'class_id'), 'r')
                if _device_class in f.readline():
                    log('Hyper-V host time sync device is {}'.format(f.name))
                    return d
            except Exception:
                pass
    except Exception:
        pass
    return None


def _check_host_sync(device_id):
    """Check if Hyper-V host clock sync is enabled"""
    statefile = os.path.join(_vmbus_dir, 'devices', device_id, 'state')
    if os.path.exists(statefile):
        try:
            f = open(statefile, 'r')
            firstline = f.readline().strip()
            result = firstline == '3'
            enabled = 'enabled' if result else 'disabled'
            log('Hyper-V host time sync is ' + enabled)
            if result:
                return device_id
            else:
                return None
        except Exception:
            log('Unable to determine Hyper-V host time sync status from {}'.format(statefile))
            return None
    else:
        return None


def _disable_host_sync(device_id):
    """Unbind the Hyper-V host clock sync driver"""
    try:
        log('Disabling Hyper-V host time sync')
        path = os.path.join(_vmbus_dir, 'drivers', 'hv_util', 'unbind')
        f = open(path, 'w')
        print(device_id, file=f)
        return True
    except Exception:
        return False


def sync_status():
    """Check Hyper-V host clock sync status; disable if detected.

    Return a sensible status message if we attempted changes."""
    device_id = _find_host_sync_device()
    if device_id and _check_host_sync(device_id):
        if _disable_host_sync(device_id):
            return 'Hyper-V host sync disabled'
        else:
            return 'Failed to disable Hyper-V host sync'
    else:
        return None
