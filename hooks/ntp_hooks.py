#!/usr/bin/python3

import sys
import charmhelpers.core.hookenv as hookenv
import charmhelpers.core.host as host
import charmhelpers.fetch as fetch
from charmhelpers.core.hookenv import UnregisteredHookError
from charmhelpers.contrib.templating.jinja import render
import shutil
import os

from charmhelpers.contrib.charmsupport import nrpe

NAGIOS_PLUGINS = '/usr/local/lib/nagios/plugins'

NTP_CONF = '/etc/ntp.conf'
NTP_CONF_ORIG = '{}.orig'.format(NTP_CONF)

hooks = hookenv.Hooks()


def get_peer_nodes():
    hosts = []
    hosts.append(hookenv.unit_get('private-address'))
    for relid in hookenv.relation_ids('ntp-peers'):
        for unit in hookenv.related_units(relid):
            hosts.append(hookenv.relation_get('private-address',
                         unit, relid))
    hosts.sort()
    return hosts


@hooks.hook('install')
def install():
    fetch.apt_update(fatal=True)
    fetch.apt_install(["ntp"], fatal=True)
    shutil.copy(NTP_CONF, NTP_CONF_ORIG)


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
@host.restart_on_change({NTP_CONF: ['ntp']})
def write_config():
    hookenv.open_port(123, protocol="UDP")
    use_iburst = hookenv.config('use_iburst')
    source = hookenv.config('source')
    orphan_stratum = hookenv.config('orphan_stratum')
    remote_sources = get_sources(source, iburst=use_iburst)
    pools = hookenv.config('pools')
    remote_pools = get_sources(pools, iburst=use_iburst)
    for relid in hookenv.relation_ids('master'):
        for unit in hookenv.related_units(relid=relid):
            u_addr = hookenv.relation_get(attribute='private-address',
                                          unit=unit, rid=relid)
            remote_sources.append({'name': u_addr, 'iburst': 'iburst'})

    peers = hookenv.config('peers')
    remote_peers = get_sources(peers, iburst=use_iburst)
    auto_peers = hookenv.config('auto_peers')
    if hookenv.relation_ids('ntp-peers') and auto_peers:
        remote_peers = get_sources(get_peer_nodes(), iburst=use_iburst,
                                   source_list=remote_peers)

    if len(remote_sources) == 0 and len(remote_peers) == 0 and len(remote_pools) == 0:
        # we have no peers/pools/servers; restore default ntp.conf provided by OS
        shutil.copy(NTP_CONF_ORIG, NTP_CONF)
    else:
        # otherwise, write our own configuration
        with open(NTP_CONF, "w") as ntpconf:
            ntpconf.write(render(os.path.basename(NTP_CONF), {
                'orphan_stratum': orphan_stratum,
                'peers': remote_peers,
                'pools': remote_pools,
                'servers': remote_sources,
            }))

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
# - https://social.msdn.microsoft.com/Forums/en-US/8c0a1026-0b02-405a-848e-628e68229eaf/i-have-a-lot-of-time-has-been-changed-in-the-journal-of-my-linux-boxes?forum=WAVirtualMachinesforWindows
_device_class = '9527e630-d0ae-497b-adce-e80ab0175caf'
_vmbus_dir = '/sys/bus/vmbus/'


def find_hyperv_host_sync_device():
    """Search for a vmbus device directory whose class matches _device_class"""
    try:
        for d in os.listdir(os.path.join(_vmbus_dir, 'devices')):
            try:
                f = open(os.path.join(_vmbus_dir, 'devices', d, 'class_id'), 'r')
                if _device_class in f.readline():
                    hookenv.log('Hyper-V host time sync device is {}'.format(f.name), level=hookenv.DEBUG)
                    return d
            except:
                pass
    except:
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
            hookenv.log('Hyper-V host time sync is ' + enabled, level=hookenv.DEBUG)
            if result:
                return device_id
            else:
                return None
        except:
            hookenv.log('Hyper-V host time sync status file {} not found'.format(statefile), level=hookenv.DEBUG)
            return None
    else:
        return None


def disable_hyperv_host_sync(device_id):
    """Unbind the Hyper-V host clock sync driver"""
    try:
        hookenv.log('Disabling Hyper-V host time sync', level=hookenv.DEBUG)
        path = os.path.join(_vmbus_dir, 'drivers', 'hv_util', 'unbind')
        f = open(path, 'w')
        print(device_id, file=f)
        return True
    except:
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
    hookenv.application_version_set(
        fetch.get_upstream_version('ntp')
    )
    if host.service_running('ntp'):
        status = 'Unit is ready'
        status_extra = hyperv_sync_status()
        if status_extra:
            status = status + '; ' + status_extra
        hookenv.status_set('active', status)
    else:
        hookenv.status_set('blocked', 'ntp not running')


if __name__ == '__main__':
    try:
        hooks.execute(sys.argv)
    except UnregisteredHookError as e:
        hookenv.log('Unknown hook {} - skipping.'.format(e))
