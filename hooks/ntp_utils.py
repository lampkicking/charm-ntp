#!/usr/bin/python
"""
After branching the charm, get the needed libs:
cd ntpmaster
~/bin/charm_helpers_sync.py -c charm-helpers-sync.yaml 

"""
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
    hookenv.log("installing ntp")
    host.apt_update(fatal=True)
    host.apt_install(["ntp"], fatal=True)
    shutil.copy("/etc/ntp.conf", "/etc/ntp.conf.orig")


def write_config():
    config=hookenv.config()

    hookenv.log("writing ntp.conf for %s."%config)
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
        hookenv.log("Adding source '%s'"%s)
        ntpconf+="server %s \n"%s
            
    ntpconf+="# The following servers are ntpmaster units \n"
    hookenv.log("Now let s mention our local masters")

    master_exist=False
    relations=hookenv.relations()
    hookenv.log("relations=%s"%relations)
    if 'master' in relations.keys() and len(relations['master'].keys()):
        hookenv.log("Master exist")
        master_exist=True
    else:
        hookenv.log("Master does not exist")


    if master_exist:

        for rel in hookenv.relation_ids('master'):
            hookenv.log("Let s check relation %s"%rel)
            related_unit=hookenv.related_units(rel)
            for u in related_unit:
                hookenv.log("related=%s"%u)
                u_addr=hookenv.relation_get(attribute='private-address', unit=u, rid=rel)
                hookenv.log("unit addr= = %s"% u_addr)
                ntpconf+="server %s iburst \n"%u_addr


    host.write_file("/etc/ntp.conf",ntpconf)

    hookenv.log("Writing ntp.cofng is done")

@hooks.hook('config-changed')
def config_changed():
    hookenv.log("config changed")
    host.service('stop',"ntp")
    write_config()
    host.service('start',"ntp")


@hooks.hook('master-relation-joined')
def master_relation_joined():
    hookenv.log("master-relation-joined")
    master_addr=hookenv.relation_get("private-address")
    hookenv.log("PLOP: we need to add the master ip %s"%master_addr)
    config_changed()


@hooks.hook('master-relation-changed')
def master_relation_changed():
    hookenv.log("master-relation-changed doing nothing.")

@hooks.hook('master-relation-departed')
def master_relation_departed():
    hookenv.log("master-relation-departed")
    master_addr=hookenv.relation_get("private-address")
    hookenv.log("PLOP: we need to remove the master ip %s"%master_addr)
    config_changed()

if __name__ == '__main__':
    try:
        hooks.execute(sys.argv)
    except UnregisteredHookError as e:
        hookenv.log('Unknown hook {} - skipping.'.format(e))
