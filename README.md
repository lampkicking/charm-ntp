Overview
--------

NTP provides network based time services to ensure synchronization of time
across computers.


Usage
-----

The ntp charm is a subordinate charm which is designed for use with other
principal charms.  In its basic mode, the ntp charm is used to configure NTP
in service units to talk directly to a set of NTP time sources:

    juju deploy ntp
    juju add-relation ntp myservice

By default this charm uses the standard set of NTP pool servers which are
configured in the relevant Ubuntu package.  In the event that you don't wish
every juju unit on your network to talk directly to the public NTP pool on the
Internet, there are several options.


Manual
======

If you already have a set of reliable, non-juju NTP servers in your network,
simply configure them as sources or peers and disable the default list of pool
servers.  For example:

    juju set ntp source="myatomiclock.local.net"
    juju set ntp peers="ntp1.local.net ntp2.local.net ntp3.local.net"
    juju set ntp pools=""

Sources, peers, and pools should be space-separated.


Multiple strata
===============

In network environments where general outbound network access to the Internet
is not avaliable or you don't have a good internal time source such as an
atomic clock, you can use selected juju units to act as an NTP service for
other units.

On machines which do have outbound NTP access to the Internet:

    juju deploy ubuntu --num-units=4
    juju deploy ntp ntp-stratum2
    juju add-relation ubuntu ntp-stratum2

In other juju environments which do not have outbound NTP access:

    juju deploy my-service
    juju deploy ntp ntp-stratum3
    juju add-relation my-service ntp-stratum3
    juju add-relation ntp-stratum2 ntp-stratum3


Auto peers
==========

Auto peers implements multiple strata automatically, by testing upstream NTP
connectivity, selecting the units with the best connectivity to comprise
the upstream stratum, and configuring the remaining hosts to receive time from
the upstream stratum.

    juju deploy my-service
    juju deploy ntp
    juju add-relation my-service ntp
    juju set ntp auto_peers=true


NTP Implementations
-------------------

Under Ubuntu 17.10 (Artful Aardvark) and earlier, the default implementation
of NTP is ntpd, from the Network Time Foundation.  Ubuntu 18.04 (Bionic
Beaver) moves to chrony as the default NTP implementation.  These decisions
are also reflected in this charm.


Monitoring
----------

This charm may be related to the NRPE charm for monitoring by Nagios.
The telegraf charm also includes support for gathering NTP metrics.
