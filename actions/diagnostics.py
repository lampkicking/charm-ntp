#!/usr/local/sbin/charm-env python3

"""
Gather NTP diagnostics for analysis by support personnel.
Author: Paul Gear
Copyright: (c) 2019 Canonical Ltd
License: GPLv3
"""

import glob
import itertools
import os
import re
import subprocess
import sys

import charmhelpers.core.hookenv as hookenv

import ntp_implementation


def command(key, cmd):
    """Return a tuple containing the given key and the results of running the command as the value.
    Strip trailing whitespace from the output."""
    output = subprocess.check_output(cmd.split())
    return (key, output.decode().rstrip())


def tail(keyprefix, pattern, regex=None):
    """Return tuples containing the key and the last 10 lines of each extant file matching the given glob pattern.
    The key will be constructed from the prefix and the resulting components of regex.
    If regex is False, construct the key from the prefix and the basename of the matched file."""
    if regex:
        match = re.compile(regex)
    for file in glob.glob(pattern):
        if os.path.exists(file):
            key = [keyprefix]
            if regex:
                m = match.match(file)
                if m is None:
                    # if the regex doesn't match, ignore this file
                    continue
                key += m.groups()
            else:
                key.append(os.path.basename(file))
            cmd = 'tail {}'.format(file)
            yield command('.'.join(key), cmd)


def kernel_actions():
    """Gather the kernel release and the current & available clock sources"""
    return itertools.chain(
        [('kernel.release', os.uname().release)],
        tail(
            'kernel',
            '/sys/devices/system/clocksource/clocksource*/*_clocksource',
            '.*/(clocksource\d+)/(available|current)',
        ),
    )


def chronyd_actions():
    """Gather chronyd sources, tracking, and log files."""
    return itertools.chain(
        [command('ntp.sources', '/usr/bin/chronyc -n sources')],
        [command('ntp.tracking', '/usr/bin/chronyc -n tracking')],
        tail('ntp.log', '/var/log/chrony/*.log', '/var/log/chrony/(.*)\.log'),
    )


def ntpd_actions():
    """Gather ntpd sources, tracking, and log files."""
    return itertools.chain(
        [command('ntp.sources', '/usr/bin/ntpq -np')],
        [command('ntp.tracking', '/usr/bin/ntpq -nc readvar')],
        tail('ntp.log', '/var/log/ntpstats/*stats'),
    )


def collect_actions():
    """Collect the action data for the current NTP implementation and kernel."""
    implementation = ntp_implementation.detect_implementation()
    if implementation is None:
        raise ValueError('No NTP implementation detected')
    elif implementation == 'chrony':
        implementation_actions = chronyd_actions
    elif implementation == 'ntp':
        implementation_actions = ntpd_actions
    else:
        raise ValueError('Unsupported NTP implementation {} detected'.format(implementation))
    return itertools.chain(
        [('ntp.implementation', implementation)],
        kernel_actions(),
        implementation_actions(),
    )


def print_action_dict(actions):
    """Print debug output"""
    for result in sorted(actions.keys()):
        print('{}: {}'.format(result, actions[result].rstrip()))


def main():
    try:
        actions = dict(collect_actions())
        if len(sys.argv) > 1 and sys.argv[1] == "--debug":
            print_action_dict(actions)
        else:
            hookenv.action_set(actions)
    except ValueError as ve:
        hookenv.action_fail(str(ve))
        sys.exit(1)
    except Exception as e:
        hookenv.action_fail('Python exception detected; please review log')
        raise e


if __name__ == '__main__':
    main()
