#!/usr/bin/python
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from charms.reactive import Endpoint
from charms.reactive import when, when_not, set_flag, clear_flag


class JujuInfoClient(Endpoint):
    @when('endpoint.{endpoint_name}.joined')
    def changed(self):
        set_flag(self.expand_name('{endpoint_name}.connected'))
        set_flag(self.expand_name('{endpoint_name}.available'))

    @when_not('endpoint.{endpoint_name}.joined')
    def broken(self):
        clear_flag(self.expand_name('{endpoint_name}.available'))
        clear_flag(self.expand_name('{endpoint_name}.connected'))

    def get_private_address(self):
        """
        Deprecated.
        """
        return self.all_joined_units[0]['private-address']

    @property
    def unit_count(self):
        """
        Number of joined units.
        """
        return len(self.all_joined_units)

    @property
    def addresses(self):
        """
        A flat list of all addresses received from related apps / units.

        This list is de-duplicated and sorted by address, so it will be stable
        for change comparison. If you need to know which app / unit an address
        comes from, see `received_addresses_map`.

        Note: This uses ingress-address, so it will work with cross-model
        relations.
        """
        addrs = {u.received_raw['ingress-address']
                 for u in self.all_joined_units}
        return list(sorted(addrs))

    @property
    def addresses_map(self):
        """
        A nested dictionary of all addresses received from related apps / units
        by app name then unit name.

        For example::

            {
                'app1': {
                    'app1/0': '10.0.0.1',
                    'app1/1': '10.0.0.2',
                }
            }

        Note: This uses ingress-address, so it will work with cross-model
        relations.
        """
        return {
            r.application_name: {
                u.unit_name: u.received_raw['ingress-address']
                for u in r.joined_units
            } for r in self.relations
        }
