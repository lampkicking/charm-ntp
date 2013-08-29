Overview
--------

NTP provides network based time services to ensure synchronization of time
across computers.

Usage
-----

The ntp charm is a subordinate charm that is design for use with other
principle charms.  It can be used in two ways:

Standalone
==========

In this mode the ntp charm is used to configure NTP in other service units to
talk directly to a set of NTP time sources:

    juju deploy ntp
    juju add-relation ntp myservice

By default this is the standard set of NTP pool servers that are configured in
the ntp Ubuntu package.

However, if you have a handy atomic clock on your network which you would prefer
to trust then you can use that instead:

    juju set ntp source=myatomiclock.local.net

You can also specify multiple sources:

    juju set ntp source="mac1.local.net mac2.local.net mac3.local.net"

Sources should be space separated.

Mastered
========

In the event that you don't wish every server on your network to talk directly to
your trusted time sources, you can use this charm in-conjunction with the ntpmaster
charm:

    juju deploy ntp
    juju deploy ntpmaster
    juju add-relation ntp ntpmaster

This allows you to gate NTP services to a single set of servers within your control.

This might have application in more secure network environments where general
outbound network access to the Internet is not avaliable or desirable and you don't
have a good internal time source such as an atomic clock.

You can of course have more that one ntpmaster:

    juju add-unit ntpmaster

All services that the ntp charm is subordinate to will be configured to sync with
all avaliable masters.

The ntpmaster charm supports the same "source" configuration that the ntp charm does.
