#!/usr/bin/python3

from charmhelpers.contrib.charmsupport import nrpe
from charmhelpers.core import hookenv, host, unitdata
from charms import layer
import charmhelpers.fetch as fetch
import os
import subprocess
import sys

from charms.reactive import (
    main,
    remove_state,
    set_state,
)

from charms.reactive.decorators import (
    hook,
    when,
    when_all,
    when_not,
)

import ntp_hyperv
import ntp_implementation
import ntp_scoring

implementation = ntp_implementation.get_implementation()


def log(msg):
    print(msg, file=sys.stderr)


def get_score():
    hookenv.status_set('maintenance', 'Retrieving suitability score')
    return ntp_scoring.get_score()


def get_relation_attributes(relation_name, attribute=None):
    """Get the list of all private-addresses from the given relation name, or, if an attribute is provided,
    a list of address/attribute pairs."""
    for relid in hookenv.relation_ids(relation_name):
        for unit in hookenv.related_units(relid=relid):
            addr = hookenv.relation_get(attribute='private-address', unit=unit, rid=relid)
            if attribute is None:
                yield addr
                continue
            attr = hookenv.relation_get(attribute=attribute, unit=unit, rid=relid)
            if attr is None:
                yield addr
            else:
                yield (addr, attr)


def get_peer_sources(topN=6):
    """
    Read the peer private addresses and their scores.
    Determine whether we're in the top N scores;
    if so, we're upstream - return None
    Otherwise, return the list of the top N peers.
    """
    if topN is None:
        topN = 6
    ourscore = get_score()
    if ourscore is None:
        return None

    hookenv.status_set('maintenance', 'Retrieving peer scores')
    peers = list(get_relation_attributes('ntp-peers', 'score'))
    hookenv.status_set('maintenance', 'Retrieved peer scores')

    if len(peers) < topN:
        # we don't have enough peers to do auto-peering
        log('[AUTO_PEER] There are only {} peers; not doing auto-peering'.format(len(peers)))
        return None

    # list of hosts with scores better than ours
    hosts = list(filter(lambda x: float(x[1]) > ourscore['score'], peers))
    log('[AUTO_PEER] {} peers better than us, topN == {}'.format(len(hosts), topN))

    # if the list is less than topN long, we're in the topN hosts
    if len(hosts) < topN:
        return None
    else:
        # sort list of hosts by score, keep only the topN
        topNhosts = sorted(hosts, key=lambda x: float(x[1]), reverse=True)[0:topN]
        # return only the host addresses
        return map(lambda x: x[0], topNhosts)


@hook('upgrade-charm')
def upgrade():
    remove_state('ntp.installed')
    # If we're upgrading from non-reactive to reactive, the
    # nrpe layer won't automatically fire, so do it manually.
    if hookenv.relation_ids('nrpe-external-master'):
        set_state('nrpe-external-master.available')


@when_not('ntp.installed')
def install():
    hookenv.status_set('maintenance', 'Updating package database')
    fetch.apt_update(fatal=True)

    pkgs = implementation.packages_to_install()
    hookenv.status_set('maintenance', 'Installing ' + ', '.join(pkgs))
    fetch.apt_install(pkgs, fatal=True)

    pkgs = ntp_scoring.packages_to_install()
    hookenv.status_set('maintenance', 'Installing ' + ', '.join(pkgs))
    fetch.apt_install(pkgs, fatal=False)

    implementation.save_config()
    hookenv.status_set('active', 'Installed required packages')
    set_state('ntp.installed')
    remove_state('ntp.configured')


def get_source_list(sources, iburst=True, source_list=None):
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


@hook('ntp-peers-relation-joined')
def set_peer_relation_score(context=None):
    """If auto_peers is enabled, get our score and add it to the peer relation."""
    if not hookenv.config('auto_peers'):
        return
    ourscore = get_score()
    if ourscore is not None:
        hookenv.status_set('maintenance', 'Setting score on peer relation')
        for relid in hookenv.relation_ids('ntp-peers'):
            hookenv.relation_set(relation_id=relid, relation_settings={'score': ourscore['score']})
        hookenv.status_set('active', 'Peer relation joined, ' + ntp_scoring.get_score_string(ourscore))


@hook('ntp-peers-relation-changed')
def peers_relation_changed(context=None):
    if hookenv.config('auto_peers'):
        remove_state('ntp.configured')


@hook('ntp-peers-relation-departed')
def peers_relation_departed(context=None):
    if hookenv.config('auto_peers'):
        remove_state('ntp.configured')


@hook('master-relation-changed')
def master_relation_changed(context=None):
    remove_state('ntp.configured')


@hook('master-relation-departed')
def master_relation_departed(context=None):
    remove_state('ntp.configured')


@when('config.changed')
def config_changed():
    remove_state('ntp.configured')


@when('ntp.installed')
@when_not('ntp.configured')
@host.restart_on_change({implementation.config_file(): [implementation.service_name()]})
def write_config():
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

    remote_sources = get_source_list(source, iburst=use_iburst)
    remote_pools = get_source_list(pools, iburst=use_iburst)
    remote_peers = get_source_list(peers, iburst=use_iburst)

    kv = unitdata.kv()

    if hookenv.relation_ids('master'):
        # use master relation in addition to configured sources
        remote_sources = get_source_list(get_relation_attributes('master'), iburst=True, source_list=remote_sources)
        kv.unset('auto_peer')
    elif auto_peers and hookenv.relation_ids('ntp-peers'):
        # use auto_peers
        auto_peer_list = get_peer_sources(hookenv.config('auto_peers_upstream'))
        if auto_peer_list is None:
            # we are upstream - use configured sources, pools, peers
            kv.set('auto_peer', 'upstream')
        else:
            # override all sources with auto_peer_list
            kv.set('auto_peer', 'client')
            remote_sources = get_source_list(auto_peer_list, iburst=use_iburst)
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

    remove_state('ntp.nrpe.configured')
    set_state('ntp.configured')
    assess_status()


@when_all('nrpe-external-master.available', 'ntpmon.installed')
@when_not('ntp.nrpe.configured')
def update_nrpe_config():
    options = layer.options('ntpmon')
    if options is None or 'install-dir' not in options:
        return

    nrpe.copy_nrpe_checks(nrpe_files_dir=options['install-dir'])

    hostname = nrpe.get_nagios_hostname()
    current_unit = nrpe.get_nagios_unit_name()
    nrpe_setup = nrpe.NRPE(hostname=hostname, primary=False)

    # remove any previously-created ntpmon checks
    nrpe_setup.remove_check(shortname="ntpmon")
    oldchecks = set(['offset', 'peers', 'reachability', 'sync'])
    for c in oldchecks:
        nrpe_setup.remove_check(shortname="ntpmon_%s" % c)

    nagios_ntpmon_checks = hookenv.config('nagios_ntpmon_checks').split()

    check_cmd = os.path.join(options['install-dir'], 'check_ntpmon.py') + ' --check ' + ' '.join(nagios_ntpmon_checks)
    unitdata.kv().set('check_cmd', check_cmd)
    nrpe_setup.add_check(
        check_cmd=check_cmd,
        description='Check NTPmon {}'.format(current_unit),
        shortname="ntpmon",
    )
    nrpe_setup.write()
    set_state('ntp.nrpe.configured')


def get_first_line(cmd):
    """Run the command and return the first line"""
    try:
        output = subprocess.check_output(cmd.split(), stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as cpe:
        output = cpe.output
    return output.decode().split('\n')[0]


def get_nagios_result(cmd):
    """Get the first line of the nagios result & strip performance data"""
    output = get_first_line(cmd)
    return output.split(' | ')[0]


@hook('update-status')
def assess_status():
    package = implementation.package_name()
    version = fetch.get_upstream_version(package)
    if version is not None:
        hookenv.application_version_set(version)

    status = []

    # service status
    if host.service_running(implementation.service_name()):
        state = 'active'
        status.append('Ready')
    else:
        state = 'blocked'
        status.append('Not running')

    # container status
    if ntp_scoring.get_virt_type() == 'container':
        status.append('time sync disabled in container')
    else:
        check_cmd = unitdata.kv().get('check_cmd')
        if check_cmd:
            status.append(get_nagios_result(check_cmd))

    # Hyper-V status
    status.append(ntp_hyperv.sync_status())

    # scoring status
    # (don't force update of the score from update-status more than once a month)
    max_age = 31 * 86400
    status.append(ntp_scoring.get_score_string(max_seconds=max_age))

    # auto_peer status
    status.append(unitdata.kv().get('auto_peer'))

    # join the non-None results in a single string
    status = package + ': ' + ', '.join([x for x in status if x])
    hookenv.status_set(state, status)


if __name__ == '__main__':
    main()
