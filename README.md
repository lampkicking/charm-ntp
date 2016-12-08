Overview
--------

NTP provides network based time services to ensure synchronization of time
across computers.

Usage
-----

The ntp charm is a subordinate charm which is designed for use with other
principal charms.  It can be used in two ways:

Standalone
==========

In this mode, the ntp charm is used to configure NTP in other service units to
talk directly to a set of NTP time sources:

    juju deploy ntp
    juju add-relation ntp myservice

By default this charm uses the standard set of NTP pool servers which are
configured in the ntp Ubuntu package.

However, if you have a handy atomic clock on your network which you would prefer
to use then you can add that:

    juju set ntp source=myatomiclock.local.net

You can also specify multiple sources and peers:

    juju set ntp source="mac1.local.net mac2.local.net mac3.local.net"
    juju set ntp peers="mac1.local.net mac2.local.net mac3.local.net"

To disable the default list of pool servers, set that to the empty string:

    juju set ntp pools=""

Sources, peers, and pools should be space separated.

If you have a large number of nodes which need to keep close sync with one
another but need to keep upstream traffic to a minimum, try auto_peers:

    juju set ntp auto_peers=true

This will select the most suitable units for connecting with upstream, and
configure the remaining units to receive time from those units.

Mastered
========

In the event that you don't wish every server on your network to talk directly to
your configured time sources, you can use this charm in-conjunction with the ntpmaster
charm:

    juju deploy ntp
    juju deploy ntpmaster
    juju add-relation ntp ntpmaster

This allows you to gate NTP services to a single set of servers within your control.

This might have application in more secure network environments where general
outbound network access to the Internet is not avaliable or desirable and you don't
have a good internal time source such as an atomic clock.

You can of course have more than one ntpmaster:

    juju add-unit ntpmaster

All services that the ntp charm is subordinate to will be configured to sync with
all avaliable masters.

The ntpmaster charm supports the same "source" configuration that the ntp charm does.

The ntp charm can also be used in place of the ntpmaster charm when coupled with
another primary charm:

    juju deploy ntp ntp-masters
    juju deploy ubuntu --num-units=4
    juju add-relation ubuntu ntp-masters
    juju set ntp-masters auto_peers=true

    juju deploy ntp
    juju deploy my-other-service --num-units=30
    juju add-relation ntp my-other-service
    juju add-relation ntp ntp-masters

This is the recommended method, since this charm provides better monitoring and
more flexible configuration than ntpmaster.
