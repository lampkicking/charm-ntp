#!/usr/bin/python

import sys
import charmhelpers.core.hookenv as hookenv
import charmhelpers.core.host as host
import charmhelpers.fetch as fetch
from charmhelpers.core.hookenv import UnregisteredHookError
import shutil
import os
from utils import (
    render_template,
)

NTP_CONF = '/etc/ntp.conf'
NTP_CONF_ORIG = '{}.orig'.format(NTP_CONF)

hooks = hookenv.Hooks()


@hooks.hook('install')
def install():
    fetch.apt_update(fatal=True)
    fetch.apt_install(["ntp"], fatal=True)
    shutil.copy(NTP_CONF, NTP_CONF_ORIG)


@hooks.hook('upgrade-charm')
@hooks.hook('config-changed')
@hooks.hook('master-relation-changed')
@hooks.hook('master-relation-departed')
@host.restart_on_change({NTP_CONF: ['ntp']})
def write_config():
    source = hookenv.config('source')
    remote_sources = []
    if source:
        sources = source.split(" ")
        for source in sources:
            if len(source) > 0:
                remote_sources.append({'name': source})
    for relid in hookenv.relation_ids('master'):
        for unit in hookenv.related_units(relid=relid):
            u_addr = hookenv.relation_get(attribute='private-address',
                                          unit=unit, rid=relid)
            remote_sources.append({'name': '%s iburst' % u_addr})

    if len(remote_sources) == 0:
        shutil.copy(NTP_CONF_ORIG, NTP_CONF)
    else:
        with open(NTP_CONF, "w") as ntpconf:
            ntpconf.write(render_template(os.path.basename(NTP_CONF),
                                          {'servers': remote_sources}))


if __name__ == '__main__':
    try:
        hooks.execute(sys.argv)
    except UnregisteredHookError as e:
        hookenv.log('Unknown hook {} - skipping.'.format(e))
