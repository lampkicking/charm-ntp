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
        for s in source.split(" "):
            if len(s) > 0:
                remote_sources.append({'name': s})
    for relid in hookenv.relation_ids('master'):
        for unit in hookenv.related_units(relid=relid):
            u_addr = hookenv.relation_get(attribute='private-address',
                                          unit=unit, rid=relid)
            remote_sources.append({'name': '%s iburst' % u_addr})

    if len(remote_sources) == 0:
        shutil.copy(NTP_CONF_ORIG, NTP_CONF)
    else:
        with open(NTP_CONF, "w") as ntpconf:
            ntpconf.write(render(os.path.basename(NTP_CONF),
                                 {'servers': remote_sources}))

    update_nrpe_config()


@hooks.hook('nrpe-external-master-relation-joined',
            'nrpe-external-master-relation-changed')
def update_nrpe_config():
    # python-dbus is used by check_upstart_job
    fetch.apt_install('python-dbus')
    if os.path.isdir(NAGIOS_PLUGINS):
        host.rsync(os.path.join(os.getenv('CHARM_DIR'), 'files', 'nagios',
                   'check_ntpd.pl'),
                   os.path.join(NAGIOS_PLUGINS, 'check_ntpd.pl'))

    hostname = nrpe.get_nagios_hostname()
    current_unit = nrpe.get_nagios_unit_name()
    nrpe_setup = nrpe.NRPE(hostname=hostname)
    nrpe.add_init_service_checks(nrpe_setup, 'ntp', current_unit)
    nrpe_setup.add_check(
        shortname="ntp_status",
        description='Check NTP status {%s}' % current_unit,
        check_cmd='check_ntpd.pl'
    )
    nrpe_setup.write()


if __name__ == '__main__':
    try:
        hooks.execute(sys.argv)
    except UnregisteredHookError as e:
        hookenv.log('Unknown hook {} - skipping.'.format(e))
