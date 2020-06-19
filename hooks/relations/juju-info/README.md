# Juju-Info Interface

The juju info interface is a special and implicit relationship that works with
any charm. It is mainly useful for subordinate charms that can add
functionality to any exisiting machine without the host charm being aware of
it.


### Flags

`{{endpoint_name}}.connected`

Note: This flag keys off of what the charm author names the relationship
endpoint, which should *not* be the name of the interface:

An example of a properly implemented relationship would resemble the following:


```yaml
requires:
  host-system:
    interface: juju-info
```

This might then be used in your charm would like:

```python
@when_any('host-system.connected')
def handle_host():
    host = endpoint_from_flag('host-system.connected')
    for address in host.addresses:
        hookenv.log('Connected to: {}'.format(address))
```

## Reference

* [Requires API documentation](docs/requires.md)
* [Provides API documentation](docs/provides.md)
* [Peers API documentation](docs/peers.md)
