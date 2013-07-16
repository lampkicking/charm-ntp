#!/usr/bin/python
import sys
import charmhelpers.core.hookenv as hookenv
import charmhelpers.core.host as host
from charmhelpers.core.hookenv import UnregisteredHookError
import os
import shutil
import subprocess
import json
from utils import (
    render_template,
)

hooks = hookenv.Hooks()

@hooks.hook('install')
def install():
    host.apt_update(fatal=True)
    host.apt_install(["ntp"], fatal=True)
    shutil.copy("/etc/ntp.conf", "/etc/ntp.conf.orig")
    hookenv.open_port(123,protocol="UDP")

def write_config():
    config=hookenv.config()
    if "source" in config.keys():
        source=config['source']
    else:
        source=''

    remote_sources=[]

    sources=source.split(" ")
    for s in sources:
        if not len(s):
            continue
        remote_sources.append({'name':s})

    relations=hookenv.relations()

    if 'master' in relations.keys() and len(relations['master'].keys()):
        for rel in hookenv.relation_ids('master'):
            related_unit=hookenv.related_units(rel)
            for u in related_unit:
                u_addr=hookenv.relation_get(attribute='private-address', unit=u, rid=rel)
                remote_sources.append({'name':'%s iburst'%u_addr})
    elif source=='':
        shutil.copy("/etc/ntp.conf.orig","/etc/ntp.conf")
        return

    ntp_context = {
        'servers': remote_sources
        }

    with open("/etc/ntp.conf","w") as ntpconf:
        ntpconf.write(render_template("ntp.conf",ntp_context))
        ntpconf.close()

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
