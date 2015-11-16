#!/usr/bin/python

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
        if isinstance(sources, basestring):
            sources = sources.split(" ")
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
    use_iburst = hookenv.config('use_iburst')
    source = hookenv.config('source')
    remote_sources = get_sources(source, iburst=use_iburst)
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

    if len(remote_sources) == 0 and len(remote_peers) == 0:
        # we have no peers/servers; restore default ntp.conf provided by OS
        shutil.copy(NTP_CONF_ORIG, NTP_CONF)
    else:
        # otherwise, write our own configuration
        with open(NTP_CONF, "w") as ntpconf:
            ntpconf.write(render(os.path.basename(NTP_CONF),
                                 {'servers': remote_sources,
                                  'peers': remote_peers,
                                  }))

    if hookenv.relation_ids('nrpe-external-master'):
        update_nrpe_config()


@hooks.hook('nrpe-external-master-relation-joined',
            'nrpe-external-master-relation-changed')
def update_nrpe_config():
    # python-dbus is used by check_upstart_job
    # python-psutil is used by check_ntpmon
    fetch.apt_install(['python-dbus', 'python-psutil'])
    nagios_ntpmon_checks = hookenv.config('nagios_ntpmon_checks').split(" ")
    if os.path.isdir(NAGIOS_PLUGINS):
        host.rsync(os.path.join(os.getenv('CHARM_DIR'), 'files', 'nagios',
                   'check_ntpmon.py'),
                   os.path.join(NAGIOS_PLUGINS, 'check_ntpmon.py'))

    hostname = nrpe.get_nagios_hostname()
    current_unit = nrpe.get_nagios_unit_name()
    nrpe_setup = nrpe.NRPE(hostname=hostname)
    nrpe.add_init_service_checks(nrpe_setup, ['ntp'], current_unit)

    allchecks = set(['offset', 'peers', 'reachability', 'sync'])

    # remove any previously-created ntpmon checks
    nrpe_setup.remove_check(shortname="ntpmon")
    for c in allchecks:
        nrpe_setup.remove_check(shortname="ntpmon_%s" % c)

    # If all checks are specified, combine them into a single check to reduce
    # Nagios noise.
    if set(nagios_ntpmon_checks) == allchecks:
        nrpe_setup.add_check(
            shortname="ntpmon",
            description='Check NTPmon {}'.format(current_unit),
            check_cmd='check_ntpmon.py'
        )
    else:
        for nc in nagios_ntpmon_checks:
            if len(nc) > 0:
                nrpe_setup.add_check(
                    shortname="ntpmon_%s" % nc,
                    description='Check NTPmon %s {%s}' % (nc, current_unit),
                    check_cmd='check_ntpmon.py --check %s' % nc
                )

    nrpe_setup.write()


if __name__ == '__main__':
    try:
        hooks.execute(sys.argv)
    except UnregisteredHookError as e:
        hookenv.log('Unknown hook {} - skipping.'.format(e))
