
TODO

- expand list of substrates
    - ob76 (maybe generic ob?), equinix, fe-lab, tokenlabs, others?
- matrix of tests
    - find a way to easily test a huge number of combinations (channels/substrates/topologies/etc)
    - (1h, 3h1c, 3h3c) x (storage / no-storage) x (all substrates) / (1 db / many dbs) (all channels)
- testing
    - ping the initial demo vm, ssh to it and test communication to internet
    - manually create more VMs in admin and demo projects, same test as above
    - run tempest with a test list (from SQA)
    - enable most plugins (they usually time out enabling)
    - test plugins as possible (SQA has some tests already)
- artifacts
    - collect openstack internal stuff
- try to pass non-conflicting IPs for simultanous clusters tests in maas?
- try to optimize equinix costs with spot instances?
- silence juju installs with spinning status / downloaded status
- maybe add dockerhub credentials to all microk8s to help avoiding timeouts?
- add proxy support (whatever sunbeam proxy support is at the moment)
- External portal with build results and artifacts

- split config in profiles/substrates with subdirs (find other repeated code)
- Remove escapes/colors/ConsoleNotes from jenkins console log?
- Improve artifacts collection, juju debug per unit, others? review sqa ones again
