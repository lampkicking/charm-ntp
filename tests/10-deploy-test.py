#!/usr/bin/python3

# This amulet code is to test the ntp charm.  NTP = Network Time Protocol.

import amulet

# The number of seconds to wait for Juju to set up the environment.
seconds = 900
ntp_server_0 = 'ntp.your.org'
ntp_server_1 = 'us.pool.ntp.org'
ntp_server_2 = 'tock.mtnlion.com'

# The ntp configuration to test.
ntp_configuration = {
    'source': ntp_server_0 + ' ' + ntp_server_1 + ' ' + ntp_server_2
}

d = amulet.Deployment()
# Add the ntp charm to the deployment.
d.add('ntp')
# Add the ntpmaster charm to the deployment.
d.add('ntpmaster')
# Add the ubuntu charm to the deployment.
d.add('ubuntu')
# Configure the ntp charm.
d.configure('ntp', ntp_configuration)

# Relate the ntp and ntpmaster charms.
d.relate('ntp:master', 'ntpmaster:master')
# Relate the ntp and the ubuntu charm.
d.relate('ntp:juju-info', 'ubuntu:juju-info')

# Deploy the environment and wait for it to setup.
try:
    d.setup(timeout=seconds)
    d.sentry.wait(seconds)
except amulet.helpers.TimeoutError:
    message = 'The environment did not setup in %d seconds.' % seconds
    # The SKIP status enables skip or fail the test based on configuration.
    amulet.raise_status(amulet.SKIP, msg=message)
except:
    raise

# Unable to get the sentry unit for ntp because it is a subordinate.
# ntp_unit = d.sentry.unit['ntp/0']

# Get the sentry unit for ntpmaster.
ntpmaster_unit = d.sentry.unit['ntpmaster/0']

# Get the sentry unit for ubuntu.
ubuntu_unit = d.sentry.unit['ubuntu/0']

# Get the public address for the system running the ntmpmaster charm.
master_public_address = ntpmaster_unit.info['public-address']
print('ntpmaster public address ' + master_public_address)
# Get the relation of ntpmaster to ntp, fail if the relation does not exist.
master_relation = ntpmaster_unit.relation('master', 'ntp:master')
# Get the private address for the system running the ntpmaster charm.
master_private_address = master_relation['private-address']
print('ntpmaster private address ' + master_private_address)

# Create a command to check the ntp service.
command = 'sudo service ntp status'
print(command)
# Run the command to see if apache2 is running.
output, code = ubuntu_unit.run(command)
print(output)
if code != 0 or output.find('NTP server is running') == -1:
    message = 'The NTP service is not running on the ubuntu unit.'
    print(message)
    amulet.raise_status(amulet.FAIL, msg=message)

# The ubuntu cloud image does not have ntp installed by default, 
# and therefore does not have the /etc/ntp.conf file.

# Read in the ntp configuration file from the ubuntu unit.
configuration_file = ubuntu_unit.file_contents('/etc/ntp.conf')
# This call will fail with an IO exception if the file does not exist.

# Search for ntp server 0 in the config file, raise an exception if not found.
configuration_file.index(ntp_server_0)
# Search for ntp server 1 in the config file, raise an exception if not found.
configuration_file.index(ntp_server_1)
# Search for ntp server 2 in the config file, raise an exception if not found.
configuration_file.index(ntp_server_2)

# Search for the ntpmaster IP address in the config file, added by relation.
configuration_file.index(master_private_address)

print('The ntp deploy test completed successfully.')
