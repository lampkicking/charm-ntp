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
        hookenv.log("No source defined, using the vanilla /etc/ntp.conf file")
        shutil.copy("/etc/ntp.conf.orig","/etc/ntp.conf")
        return 

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

    if not len(source):
        hookenv.log("No source set, restoring original ntp.conf")
        shutil.copy("/etc/ntp.conf.orig","/etc/ntp.conf")
        return
    else:
        hookenv.log("This is a regular server with existing sources")
        sources=source.split(",")
        for s in sources:
            hookenv.log("Adding source '%s'"%s)
            ntpconf+="server %s \n"%s

    host.write_file("/etc/ntp.conf",ntpconf)

    
@hooks.hook('config-changed')
def config_changed():
    hookenv.log("config changed")
    config=hookenv.config()


    if hookenv.in_relation_hook():
        hookenv.log("SO WE ARE IN A RELATION HOOK")
        hookenv.log("COIN relation=%s"%hookenv.relation_get())
    else:
        hookenv.log("WE ARE NOT IN A RELATION HOOK")

    hookenv.log("this is unit %s "%hookenv.local_unit())
    for rel in hookenv.relation_ids('peer'):
        hookenv.log("Let s check relation %s"%rel)
        related_unit=hookenv.related_units(rel)
        for u in related_unit:
            hookenv.log("related=%s"%u)

    host.service('stop',"ntp")
    if "source" in config.keys():
        source=config['source']
        hookenv.log("source=%s"%source)
        write_config()
    else:
        hookenv.log("No source set, putting back the default /etc/ntp.conf file")
        shutil.copy("/etc/ntp.conf.orig","/etc/ntp.conf")
    host.service('start',"ntp")



if __name__ == '__main__':
    try:
        hooks.execute(sys.argv)
    except UnregisteredHookError as e:
        hookenv.log('Unknown hook {} - skipping.'.format(e))
