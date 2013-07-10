#!/usr/bin/python
import sys
import charmhelpers.core.hookenv as hookenv
import charmhelpers.core.host as host
from charmhelpers.core.hookenv import UnregisteredHookError
import os
import shutil
import subprocess
import json

hooks = hookenv.Hooks()

@hooks.hook('install')
def install():
    host.apt_update(fatal=True)
    host.apt_install(["ntp"], fatal=True)
    shutil.copy("/etc/ntp.conf", "/etc/ntp.conf.orig")


def write_config():
    config=hookenv.config()
    if "source" in config.keys():
        source=config['source']
    else:
        source=''

    ntpconf="# juju generated ntp configuration\n"
    ntpconf+="driftfile /var/lib/ntp/ntp.drift\n"
    ntpconf+="statistics loopstats peerstats clockstats\n"
    ntpconf+="filegen loopstats file loopstats type day enable\n"
    ntpconf+="filegen peerstats file peerstats type day enable\n"
    ntpconf+="filegen clockstats file clockstats type day enable\n"
    ntpconf+="restrict -4 default kod notrap nomodify nopeer noquery\n"
    ntpconf+="restrict -6 default kod notrap nomodify nopeer noquery\n"
    ntpconf+="restrict 127.0.0.1\n"
    ntpconf+="restrict ::1\n"
    ntpconf+="# SERVERS\n"

    sources=source.split(",")
    for s in sources:
        if not len(s):
            continue
        ntpconf+="server %s \n"%s
            
    ntpconf+="# The following servers are ntpmaster units \n"

    relations=hookenv.relations()

    if 'master' in relations.keys() and len(relations['master'].keys()):
        for rel in hookenv.relation_ids('master'):
            hookenv.log("Let s check relation %s"%rel)
            related_unit=hookenv.related_units(rel)
            for u in related_unit:
                u_addr=hookenv.relation_get(attribute='private-address', unit=u, rid=rel)
                ntpconf+="server %s iburst \n"%u_addr

    elif source=='':
        hookenv.log("No master nor source set, let s use the vanilla conf file")
        shutil.copy("/etc/ntp.conf.orig","/etc/ntp.conf")
        return

    host.write_file("/etc/ntp.conf",ntpconf)

@hooks.hook('config-changed')
def config_changed():
    host.service('stop',"ntp")
    write_config()
    host.service('start',"ntp")


@hooks.hook('master-relation-joined')
def master_relation_joined():
    config_changed()


@hooks.hook('master-relation-changed')
def master_relation_changed():
    return

@hooks.hook('master-relation-departed')
def master_relation_departed():
    master_addr=hookenv.relation_get("private-address")
    config_changed()

if __name__ == '__main__':
    try:
        hooks.execute(sys.argv)
    except UnregisteredHookError as e:
        hookenv.log('Unknown hook {} - skipping.'.format(e))
