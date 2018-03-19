Overview
--------

NTP provides network based time services to ensure synchronization of time
across computers.

Usage
-----

The ntp charm is a subordinate charm which is designed for use with other
principal charms.  It can be used in two ways:

In this mode, the ntp charm is used to configure NTP in other service units to
talk directly to a set of NTP time sources:

    juju deploy ntp
    juju add-relation ntp myservice

By default this charm uses the standard set of NTP pool servers which are
configured in the relevant Ubuntu package.  In the event that you don't wish
every juju unit on your network to talk directly to the public NTP pool on the
Internet (the default configuration), there are several options.


Manual
======

If you already have a set of reliable, non-juju NTP servers in your network,
simply configure them as sources or peers and disable the default list of pool
servers.  For example:

    juju set ntp source="myatomiclock.local.net"
    juju set ntp peers="ntp1.local.net ntp2.local.net ntp3.local.net"
    juju set ntp pools=""

Sources, peers, and pools should be space-separated.


Multi-tier
==========

This might have application in more secure network environments where general
outbound network access to the Internet is not avaliable or desirable and you
don't have a good internal time source such as an atomic clock.

The ntp charm can also be used in place of the ntpmaster charm when coupled
with another primary charm:

    juju deploy ntp ntp-masters
    juju deploy ubuntu --num-units=4
    juju add-relation ubuntu ntp-masters
    juju set ntp-masters auto_peers=true

    juju deploy ntp
    juju deploy my-other-service --num-units=30
    juju add-relation ntp my-other-service
    juju add-relation ntp ntp-masters

This is the recommended method, since this charm provides better monitoring
and more flexible configuration than ntpmaster.

Auto peers
----------

If you have a large number of nodes which need to keep close sync with one
another but need to keep upstream traffic to a minimum, try auto_peers:

    juju set ntp auto_peers=true

This will select the most suitable units for connecting with upstream, and
configure the remaining units to receive time from those units.
