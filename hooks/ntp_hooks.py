#!/usr/bin/python

import sys
import charmhelpers.core.hookenv as hookenv
import charmhelpers.core.host as host
import charmhelpers.fetch as fetch
from charmhelpers.core.hookenv import UnregisteredHookError
from charmhelpers.contrib.templating.jinja import render
import shutil
import os


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
    remote_sources = []
    if source:
        for s in source.split(" "):
            if len(s) > 0:
                if use_iburst:
                    remote_sources.append({'name': '%s iburst' % s})
                else:
                    remote_sources.append({'name': s})
    for relid in hookenv.relation_ids('master'):
        for unit in hookenv.related_units(relid=relid):
            u_addr = hookenv.relation_get(attribute='private-address',
                                          unit=unit, rid=relid)
            remote_sources.append({'name': '%s iburst' % u_addr})

    auto_peers = hookenv.config('auto_peers')
    peers = hookenv.config('peers')
    remote_peers = []
    if peers:
        for p in peers.split(" "):
            if len(p) > 0:
                if use_iburst:
                    remote_peers.append({'name': '%s iburst' % p})
                else:
                    remote_peers.append({'name': p})
    if hookenv.relation_ids('ntp-peers'):
        if auto_peers:
            for rp in get_peer_nodes():
                if use_iburst:
                    remote_peers.append({'name': '%s iburst' % rp})
                else:
                    remote_peers.append({'name': rp})

    total = len(remote_sources) + len(remote_peers)
    total_sources = hookenv.config('total_sources')
    hookenv.log("Total remote ntp sources: {}".format(total))
    if total < total_sources:
        hookenv.log("WARNING: You should  have {} or more remote \
                    ntp sources configured!".format(total))

    if len(remote_sources) == 0:
        shutil.copy(NTP_CONF_ORIG, NTP_CONF)
    else:
        with open(NTP_CONF, "w") as ntpconf:
            ntpconf.write(render(os.path.basename(NTP_CONF),
                                 {'servers': remote_sources,
                                  'peers': remote_peers}))


if __name__ == '__main__':
    try:
        hooks.execute(sys.argv)
    except UnregisteredHookError as e:
        hookenv.log('Unknown hook {} - skipping.'.format(e))
