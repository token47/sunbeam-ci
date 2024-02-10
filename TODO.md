
TODO

- expand list of substrates
    - ob76 (maybe generic ob?), equinix, fe-lab, others?
- matrix of tests
    - find a way to easily test a huge number of combinations (channels/substrates/topologies/etc)
    - with 1 to 8 machines in sensible configs (1 control, 3 controls, with/withoug ceph, etc.)
    - (1h, 3h1c, 3h3c, 6h3c) x (storage / no-storage) x (all substrates) x (all channels) x (1 db / many dbs)
- maybe add dockerhub credentials to all microk8s to help avoiding timeouts?
- add proxy support (whatever sunbeam proxy support is at the moment)
- testing
    - ping the initial demo vm, ssh to it and test communication to internet
    - manually create more VMs in admin and demo projects, same test as above
    - run tempest with a test list (from SQA)
- capture evidences
    - most openstack resources (servers, networks, subnets, routers, images, flavors, etc.)
    - juju status, juju debug-logs?, microceph details, microk8s details, sunbeam logs (SQA has more)
- plugins
    - enable most plugins (they usually time out enabling)
    - test plugins as possible (SQA has some tests already)
- try to pass non-conflicting IPs for simultanous tests in maas?
    - although this might not be a problem for single machine tests
- try to optimize equinix costs with spot instances
- silence juju installs with spinning status / downloaded status
