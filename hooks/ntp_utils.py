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
import pickle

"""
This charm needs to maintain a set of exisitng master ntp unit
as each one needs to be in a server line in the /etc/ntp.conf file
Let s store this set in a pickle.
"""

def get_data_to_pickle(data,filename):
    hookenv.log("Saving data to file:%s"%data)
    output=open(filename, 'wb')
    pickle.dump(data,output)    
    output.close()

def get_data_from_pickle(filename):
    if not os.path.exists(filename):
        get_data_to_pickle(set(),filename)

    data=open(filename, 'rb')
    out=pickle.load(data)
    data.close()
    return out

servers_pickle_file="/tmp/servers_pickle.bin"
servers_pickle_lock="/tmp/servers_pickle.lock"


hooks = hookenv.Hooks()

@hooks.hook('install')
def install():
    hookenv.log("installing ntp")
    host.apt_update(fatal=True)
    host.apt_install(["ntp"], fatal=True)
    shutil.copy("/etc/ntp.conf", "/etc/ntp.conf.orig")
    if not os.path.exists(servers_pickle_file):
        get_data_to_pickle(set(),servers_pickle_file)


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
            
        hookenv.log("Now let s mention our local master")
        masters=get_data_from_pickle(servers_pickle_file)
        for s in masters:
            ntpconf+="server "+s+" iburst\n"


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


@hooks.hook('master-relation-joined')
def master_relation_joined():
    hookenv.log("master-relation-joined")
    master_addr=hookenv.relation_get("private-address")
    hookenv.log("PLOP: we need to add the master ip %s"%master_addr)
    while os.path.exists(servers_pickle_lock):
        hookenv.log("Some other process try to access the pickle jar. Let s wait a bit.)")
        time.sleep(1)

    fl = os.open( servers_pickle_lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL)

    masters=get_data_from_pickle(servers_pickle_file)
    hookenv.log("PLOP data from disk is %s"%masters)
    masters.add(master_addr)
    get_data_to_pickle(masters,servers_pickle_file)

    os.close(fl)
    os.remove(servers_pickle_lock)

    config_changed()


@hooks.hook('master-relation-changed')
def master_relation_changed():
    hookenv.log("master-relation-changed doing nothing.")

@hooks.hook('master-relation-departed')
def master_relation_departed():
    hookenv.log("master-relation-departed")
    master_addr=hookenv.relation_get("private-address")
    hookenv.log("PLOP: we need to remove the master ip %s"%master_addr)
    while os.path.exists(servers_pickle_lock):
        hookenv.log("Some other process try to access the pickle jar. Let s wait a bit.)")
        time.sleep(1)

    fl = os.open( servers_pickle_lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL)

    masters=get_data_from_pickle(servers_pickle_file)
    hookenv.log("PLOP data from disk is %s"%masters)
    masters.remove(master_addr)
    get_data_to_pickle(masters,servers_pickle_file)

    os.close(fl)
    os.remove(servers_pickle_lock)

    config_changed()



if __name__ == '__main__':
    try:
        hooks.execute(sys.argv)
    except UnregisteredHookError as e:
        hookenv.log('Unknown hook {} - skipping.'.format(e))
