#!/usr/bin/python3

from charmhelpers.contrib.charmsupport import nrpe
from charmhelpers.core import hookenv, host, unitdata
import charmhelpers.fetch as fetch
import os

from charms.reactive import (
    main,
    remove_state,
    set_state,
)

from charms.reactive.decorators import (
    hook,
    when,
    when_not,
)

import ntp_hyperv
import ntp_implementation
import ntp_scoring

NAGIOS_PLUGINS = '/usr/local/lib/nagios/plugins'

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
    hookenv.status_set('maintentance', 'Retrieving suitability score')
    ourscore = ntp_scoring.get_score()
    if ourscore is None:
        hookenv.log('[AUTO_PEER] Our score cannot be determined - check logs for reason')
        return None

    hookenv.status_set('maintentance', 'Retrieving peer suitability scores')
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


@when_not('ntp.installed')
def install():
    hookenv.status_set('maintentance', 'Updating package database')
    fetch.apt_update(fatal=True)

    pkgs = ntp_scoring.packages_to_install()
    hookenv.status_set('maintentance', 'Installing ' + ', '.join(pkgs))
    fetch.apt_install(pkgs, fatal=False)

    pkgs = implementation.packages_to_install()
    hookenv.status_set('maintentance', 'Installing ' + ', '.join(pkgs))
    fetch.apt_install(pkgs, fatal=True)

    implementation.save_config()
    hookenv.status_set('active', 'Installed required packages')
    set_state('ntp.installed')


@hook('upgrade-charm')
@hook('master-relation-changed')
@hook('master-relation-departed')
@hook('ntp-peers-relation-joined')
@hook('ntp-peers-relation-changed')
@when('config.changed')
def reconfigure():
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

    remote_sources = get_sources(source, iburst=use_iburst)
    remote_pools = get_sources(pools, iburst=use_iburst)
    remote_peers = get_sources(peers, iburst=use_iburst)

    kv = unitdata.kv()

    if hookenv.relation_ids('master'):
        # use master relation in addition to configured sources
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

    # FIXME: remove
    if hookenv.relation_ids('nrpe-external-master'):
        update_nrpe_config()

    remove_state('ntp.configured')
    assess_status()


# FIXME: move to ntpmon layer
@hook('nrpe-external-master-relation-joined')
@hook('nrpe-external-master-relation-changed')
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

    # Hyper-V status
    status.append(ntp_hyperv.sync_status())

    # scoring status
    # (don't force update of the score from update-status more than once a month)
    max_age = 31 * 86400
    status.append(ntp_scoring.get_score_string(max_seconds=max_age))

    # auto_peer status
    status.append(unitdata.kv().get('auto_peer'))

    # join the non-None results in a single string
    status = package + ': ' + ', '.join([x for x in status if x is not None])
    hookenv.status_set(state, status)


if __name__ == '__main__':
    main()
