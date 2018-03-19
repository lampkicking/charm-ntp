#!/usr/bin/python3

from charmhelpers.contrib.charmsupport import nrpe
from charmhelpers.core import hookenv, host, unitdata
import charmhelpers.fetch as fetch
import os
import sys

import ntp_implementation
import ntp_scoring

NAGIOS_PLUGINS = '/usr/local/lib/nagios/plugins'

hooks = hookenv.Hooks()
implementation = ntp_implementation.get_implementation()


def get_peer_sources(topN=6):
    """
    Get our score and put it on the peer relation.
    Read the peer private addresses and their scores.
    Determine whether we're in the top N scores;
    if so, we're upstream - return None
    Otherwise, return the list of the top N peers.
    """
    if topN is None:
        topN = 6
    ourscore = ntp_scoring.get_score()
    if ourscore is None:
        hookenv.log('[AUTO_PEER] Our score cannot be determined - check logs for reason')
        return None

    peers = []
    for relid in hookenv.relation_ids('ntp-peers'):
        hookenv.relation_set(relation_id=relid, relation_settings={'score': ourscore['score']})
        for unit in hookenv.related_units(relid):
            addr = hookenv.relation_get('private-address', unit, relid)
            peerscore = hookenv.relation_get('score', unit, relid)
            if peerscore is not None:
                peers.append((addr, float(peerscore)))

    if len(peers) < topN:
        # we don't have enough peers to do auto-peering
        hookenv.log('[AUTO_PEER] There are only {} peers; not doing auto-peering'.format(len(peers)))
        return None

    # list of hosts with scores better than ours
    hosts = list(filter(lambda x: x[1] > ourscore['score'], peers))
    hookenv.log('[AUTO_PEER] {} peers better than us, topN == {}'.format(len(hosts), topN))

    # if the list is less than topN long, we're in the topN hosts
    if len(hosts) < topN:
        return None
    else:
        # sort list of hosts by score, keep only the topN
        topNhosts = sorted(hosts, key=lambda x: x[1], reverse=True)[0:topN]
        # return only the host addresses
        return map(lambda x: x[0], topNhosts)


@hooks.hook('install')
def install():
    fetch.apt_update(fatal=True)
    ntp_scoring.install_packages()
    fetch.apt_install(implementation.packages_to_install(), fatal=True)
    implementation.save_config()


def get_sources(sources, iburst=True, source_list=None):
    if source_list is None:
        source_list = []
    if sources:
        # allow both strings and lists
        if isinstance(sources, str):
            sources = sources.split()
        for s in sources:
            if len(s) > 0:
                if iburst:
                    source_list.append({'name': s, 'iburst': 'iburst'})
                else:
                    source_list.append({'name': s, 'iburst': ''})
    return source_list


@hooks.hook('upgrade-charm')
@hooks.hook('config-changed')
@hooks.hook('master-relation-changed')
@hooks.hook('master-relation-departed')
@hooks.hook('ntp-peers-relation-joined',
            'ntp-peers-relation-changed')
@host.restart_on_change({implementation.config_file(): [implementation.service_name()]})
def write_config():
    ntp_scoring.install_packages()

    if ntp_scoring.get_virt_type() == 'container':
        is_container = 1
    else:
        is_container = 0

    implementation.set_startup_options({
        'is_container': is_container,
    })

    host.service_resume(implementation.service_name())
    hookenv.open_port(123, protocol="UDP")

    use_iburst = hookenv.config('use_iburst')
    orphan_stratum = hookenv.config('orphan_stratum')
    source = hookenv.config('source')
    pools = hookenv.config('pools')
    peers = hookenv.config('peers')
    auto_peers = hookenv.config('auto_peers')

    remote_sources = get_sources(source, iburst=use_iburst)
    remote_pools = get_sources(pools, iburst=use_iburst)
    remote_peers = get_sources(peers, iburst=use_iburst)

    kv = unitdata.kv()
    hookenv.atexit(kv.flush)

    if hookenv.relation_ids('master'):
        # use master relation only
        for relid in hookenv.relation_ids('master'):
            for unit in hookenv.related_units(relid=relid):
                u_addr = hookenv.relation_get(attribute='private-address',
                                              unit=unit, rid=relid)
                remote_sources.append({'name': u_addr, 'iburst': 'iburst'})
    elif auto_peers and hookenv.relation_ids('ntp-peers'):
        # use auto_peers
        auto_peer_list = get_peer_sources(hookenv.config('auto_peers_upstream'))
        if auto_peer_list is None:
            # we are upstream - use configured sources, pools, peers
            kv.set('auto_peer', 'upstream')
        else:
            # override all sources with auto_peer_list
            kv.set('auto_peer', 'client')
            remote_sources = get_sources(auto_peer_list, iburst=use_iburst)
            remote_pools = []
            remote_peers = []
    else:
        # use configured sources, pools, peers
        kv.unset('auto_peer')

    if len(remote_sources) == 0 and len(remote_peers) == 0 and len(remote_pools) == 0:
        # we have no peers/pools/servers; restore default config
        implementation.restore_config()
    else:
        # otherwise, write our own configuration
        implementation.set_config({
            'is_container': is_container,
            'orphan_stratum': orphan_stratum,
            'peers': remote_peers,
            'pools': remote_pools,
            'servers': remote_sources,
        })

    if hookenv.relation_ids('nrpe-external-master'):
        update_nrpe_config()
    assess_status()


@hooks.hook('nrpe-external-master-relation-joined',
            'nrpe-external-master-relation-changed')
def update_nrpe_config():
    # python-dbus is used by check_upstart_job
    # python-psutil is used by check_ntpmon
    fetch.apt_install(['python-dbus', 'python-psutil'])
    nagios_ntpmon_checks = hookenv.config('nagios_ntpmon_checks').split()
    if os.path.isdir(NAGIOS_PLUGINS):
        host.rsync(os.path.join(os.getenv('CHARM_DIR'), 'files', 'nagios',
                   'check_ntpmon.py'),
                   os.path.join(NAGIOS_PLUGINS, 'check_ntpmon.py'))

    hostname = nrpe.get_nagios_hostname()
    current_unit = nrpe.get_nagios_unit_name()
    nrpe_setup = nrpe.NRPE(hostname=hostname, primary=False)

    allchecks = set(['offset', 'peers', 'reachability', 'sync'])

    # remove any previously-created ntpmon checks
    nrpe_setup.remove_check(shortname="ntpmon")
    for c in allchecks:
        nrpe_setup.remove_check(shortname="ntpmon_%s" % c)

    nrpe_setup.add_check(
        shortname="ntpmon",
        description='Check NTPmon {}'.format(current_unit),
        check_cmd=('check_ntpmon.py --checks ' +
                   ' '.join(nagios_ntpmon_checks))
    )
    nrpe_setup.write()


# Hyper-V host clock sync handling - workaround until https://bugs.launchpad.net/bugs/1676635 is SRUed for xenial
# See also:
# - https://patchwork.kernel.org/patch/9525945/
# - https://social.msdn.microsoft.com/Forums/en-US/8c0a1026-0b02-405a-848e-628e68229eaf/i-have-a-lot-of-time-has-been-changed-in-the-journal-of-my-linux-boxes?forum=WAVirtualMachinesforWindows # NOQA: E501
_device_class = '9527e630-d0ae-497b-adce-e80ab0175caf'
_vmbus_dir = '/sys/bus/vmbus/'


def find_hyperv_host_sync_device():
    """Search for a vmbus device directory whose class matches _device_class"""
    try:
        for d in os.listdir(os.path.join(_vmbus_dir, 'devices')):
            try:
                f = open(os.path.join(_vmbus_dir, 'devices', d, 'class_id'), 'r')
                if _device_class in f.readline():
                    hookenv.log('Hyper-V host time sync device is {}'.format(f.name))
                    return d
            except Exception:
                pass
    except Exception:
        pass
    return None


def check_hyperv_host_sync(device_id):
    """Check if Hyper-V host clock sync is enabled"""
    statefile = os.path.join(_vmbus_dir, 'devices', device_id, 'state')
    if os.path.exists(statefile):
        try:
            f = open(statefile, 'r')
            firstline = f.readline().strip()
            result = firstline == '3'
            enabled = 'enabled' if result else 'disabled'
            hookenv.log('Hyper-V host time sync is ' + enabled)
            if result:
                return device_id
            else:
                return None
        except Exception:
            hookenv.log('Hyper-V host time sync status file {} not found'.format(statefile))
            return None
    else:
        return None


def disable_hyperv_host_sync(device_id):
    """Unbind the Hyper-V host clock sync driver"""
    try:
        hookenv.log('Disabling Hyper-V host time sync')
        path = os.path.join(_vmbus_dir, 'drivers', 'hv_util', 'unbind')
        f = open(path, 'w')
        print(device_id, file=f)
        return True
    except Exception:
        return False


def hyperv_sync_status():
    """Check Hyper-V host clock sync status; disable if detected.
    Report a sensible status message if we attempted changes."""
    device_id = find_hyperv_host_sync_device()
    if device_id and check_hyperv_host_sync(device_id):
        if disable_hyperv_host_sync(device_id):
            return 'Hyper-V host sync disabled'
        else:
            return 'Failed to disable Hyper-V host sync'
    else:
        return None


@hooks.hook('update-status')
def assess_status():
    package = implementation.package_name()
    version = fetch.get_upstream_version(package)
    if version is not None:
        hookenv.application_version_set(version)

    # base status
    status = package + ': '

    # append service status
    if host.service_running(implementation.service_name()):
        state = 'active'
        status += 'Ready'
    else:
        state = 'blocked'
        status += 'Not running'

    # append container status
    if ntp_scoring.get_virt_type() == 'container':
        status += ', time sync disabled in container'

    # append Hyper-V status
    hyperv_status = hyperv_sync_status()
    if hyperv_status is not None:
        status += ', ' + hyperv_status

    # append scoring status
    # (don't force update of the score from update-status more than once a month)
    max_age = 31 * 86400
    scorestr = ntp_scoring.get_score_string(max_seconds=max_age)
    if scorestr is not None:
        status += ', ' + scorestr

    # append auto_peer status
    autopeer = unitdata.kv().get('auto_peer')
    if autopeer is not None:
        status += ' [{}]'.format(autopeer)

    hookenv.status_set(state, status)


if __name__ == '__main__':
    try:
        hooks.execute(sys.argv)
    except hookenv.UnregisteredHookError as e:
        hookenv.log('Unknown hook {} - skipping.'.format(e))
