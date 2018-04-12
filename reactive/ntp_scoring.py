
# Copyright (c) 2017 Canonical Ltd
# License: GPLv3
# Author: Paul Gear

# This module retrieves the score calculated in ntp_source_score, and
# creates an overall node weighting based on the machine type (bare metal,
# container, or VM) and software running locally.  It reduces the score
# for nodes with OpenStack ceph, nova, or swift services running, in order
# to decrease the likelihood that they will be selected as upstreams.

from charmhelpers.core import hookenv, unitdata
import json
import time

from ntp_hooks import log
import ntp_source_score


def packages_to_install():
    return ["facter", "ntpdate", "python3-psutil", "virt-what"]


def get_virt_type():
    """Work out what type of environment we're running in"""
    for line in ntp_source_score.run_cmd('facter virtual'):
        fields = str(line).split()
        if len(fields) > 0:
            if fields[0] in ['physical', 'xen0']:
                return 'physical'
            if fields[0] in ['docker', 'lxc', 'openvz']:
                return 'container'
    # Anything not one of the above-mentioned types is assumed to be a VM
    return 'vm'


def get_virt_multiplier():
    virt_type = get_virt_type()
    if virt_type == 'container':
        # containers should be synchronized from their host
        return -1
    elif virt_type == 'physical':
        log('[SCORE] running on physical host - score bump 25%')
        return 1.25
    else:
        log('[SCORE] probably running in a VM - score bump 0%')
        return 1


def get_package_divisor():
    """Check for running ceph, swift, & nova-compute services,
    and increase divisor for each."""
    try:
        import psutil
    except Exception:
        # If we can't read the process table, assume a worst-case.
        # (Normally, if every process is running, this will return
        # 1.1 * 1.1 * 1.25 * 1.25 = 1.890625.)
        return 2

    # set the weight for each process (regardless of how many there are running)
    running = {}
    for p in psutil.process_iter():
        name = p.name() if psutil.version_info >= (2, 0) else p.name
        if name.startswith('nova-compute'):
            running['nova-compute'] = 1.25
        if name.startswith('ceph-osd'):
            running['ceph-osd'] = 1.25
        elif name.startswith('ceph-'):
            running['ceph'] = 1.1
        elif name.startswith('swift-'):
            running['swift'] = 1.1

    # increase the divisor for each discovered process type
    divisor = 1
    for r in running:
        log('[SCORE] %s running - score divisor %.3f' % (r, running[r]))
        divisor *= running[r]
    return divisor


def check_score(seconds=None):
    if seconds is None:
        seconds = time.time()
    score = {
        'divisor': 1,
        'multiplier': 0,
        'score': -999,
        'time': seconds,
    }

    # skip scoring if we have an explicitly configured master
    relation_sources = hookenv.relation_ids('master')
    score['master-relations'] = len(relation_sources)
    if relation_sources is not None and len(relation_sources) > 0:
        log('[SCORE] master relation configured - skipped scoring')
        return score

    # skip scoring if we're in a container
    multiplier = get_virt_multiplier()
    score['multiplier'] = multiplier
    if multiplier <= 0:
        log('[SCORE] running in a container - skipped scoring')
        return score

    # skip scoring if auto_peers is off
    auto_peers = hookenv.config('auto_peers')
    score['auto-peers'] = auto_peers
    if not auto_peers:
        log('[SCORE] auto_peers is disabled - skipped scoring')
        return score

    # skip scoring if we have no sources
    sources = hookenv.config('source').split()
    peers = hookenv.config('peers').split()
    pools = hookenv.config('pools').split()
    host_list = sources + peers + pools
    if len(host_list) == 0:
        log('[SCORE] No sources configured')
        return score

    # Now that we've passed all those checks, check upstreams, calculate a score, and return the result
    divisor = get_package_divisor()
    score['divisor'] = divisor
    score['host-list'] = host_list
    score['raw'] = ntp_source_score.get_source_score(host_list, verbose=True)
    score['score'] = score['raw'] * multiplier / divisor
    log('[SCORE] Suitability score: %.3f' % (score['score'],))
    return score


def get_score(max_seconds=86400):
    kv = unitdata.kv()
    score = kv.get('ntp_score')
    if score is not None:
        saved_time = score.get('time', 0)
    else:
        saved_time = 0

    now = time.time()
    if score is None or now - saved_time > max_seconds:
        score = check_score(now)
        kv.set('ntp_score', score)
        log('[SCORE] saved %s' % (json.dumps(score),))

    return score


def get_score_string(score=None, max_seconds=86400):
    if score is None:
        score = get_score(max_seconds)
    if 'raw' not in score:
        return None
    return 'score %.3f (%.1f) at %s' % (
        score['score'],
        score['multiplier'] / score['divisor'],
        time.ctime(score['time'])
    )
