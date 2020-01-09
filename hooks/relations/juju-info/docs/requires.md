<h1 id="requires">requires</h1>


<h1 id="requires.JujuInfoClient">JujuInfoClient</h1>

```python
JujuInfoClient(endpoint_name, relation_ids=None)
```

<h2 id="requires.JujuInfoClient.addresses">addresses</h2>


A flat list of all addresses received from related apps / units.

This list is de-duplicated and sorted by address, so it will be stable
for change comparison. If you need to know which app / unit an address
comes from, see `received_addresses_map`.

Note: This uses ingress-address, so it will work with cross-model
relations.

<h2 id="requires.JujuInfoClient.addresses_map">addresses_map</h2>


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

<h2 id="requires.JujuInfoClient.unit_count">unit_count</h2>


Number of joined units.

<h2 id="requires.JujuInfoClient.get_private_address">get_private_address</h2>

```python
JujuInfoClient.get_private_address()
```

Deprecated.

