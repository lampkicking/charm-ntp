
# Copyright (c) 2018 Canonical Ltd
# License: GPLv3
# Author: Paul Gear

# NTP implementation details

import charmhelpers.contrib.templating.jinja as templating
import charmhelpers.core.host
import charmhelpers.osplatform
import os.path
import shutil


class NTPImplementation:
    """Base class for NTP implementations."""

    def config_file(self):
        pass

    def _config_file_backup(self):
        return self.config_file() + ".bak"

    def _config_file_orig(self):
        return self.config_file() + ".orig"

    def _config_file_template(self):
        pass

    def package_name(self):
        pass

    def packages_to_install(self):
        return [self.package_name()]

    def restore_config(self):
        for path in [self._config_file_orig(), self._config_file_backup()]:
            if os.path.exists(path):
                shutil.copy(path, self.config_file())

    def save_config(self):
        backup = self._config_file_backup()
        if not os.path.exists(backup):
            shutil.copy(self.config_file(), backup)

    def service_name(self):
        pass

    def set_config(self, config):
        with open(self.config_file(), "w") as conffile:
            conffile.write(templating.render(self._config_file_template(), config))

    def set_startup_options(self, config):
        with open(self._startup_config_file(), "w") as startup:
            startup.write(templating.render(self._startup_template_file(), config))

    def _startup_config_file(self):
        pass

    def _startup_template_file(self):
        pass


class Chronyd(NTPImplementation):

    def config_file(self):
        return "/etc/chrony/chrony.conf"

    def _config_file_orig(self):
        return "/usr/share/chrony/chrony.conf"

    def _config_file_template(self):
        return "chrony.conf"

    def package_name(self):
        return "chrony"

    def service_name(self):
        return "chrony"

    def _startup_config_file(self):
        return "/etc/default/chrony"

    def _startup_template_file(self):
        return "chrony.default"


class NTPd(NTPImplementation):

    def config_file(self):
        return "/etc/ntp.conf"

    def _config_file_template(self):
        return "ntp.conf"

    def package_name(self):
        return "ntp"

    def service_name(self):
        return "ntp"

    def _startup_config_file(self):
        return "/etc/default/ntp"

    def _startup_template_file(self):
        return "ntp.default"


def get_implementation(implementation_name=None):
    if implementation_name.lower() == 'chrony':
        return Chronyd()
    if implementation_name.lower() == 'ntpd':
        return NTPd()

    # anything else: auto mode
    platform = charmhelpers.osplatform.get_platform()
    version = float(charmhelpers.core.host.lsb_release()['DISTRIB_RELEASE'])

    if platform == 'ubuntu':
        if version > 18:
            # Ubuntu 18.04 or later: use chronyd
            return Chronyd()
        else:
            # Ubuntu 17.10 or earlier: use ntpd
            return NTPd()
    elif platform == 'centos':
        # CentOS: use chronyd
        return Chronyd()
    else:
        # something else: use ntpd
        return NTPd()
