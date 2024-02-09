
TODO

- expand list of substrates
    - ob76 (maybe generic ob?), equinix, fe-lab, others?
- matrix of tests
    - find a way to easily test a huge number of combinations (channels/substrates/topologies/etc)
    - with 1 to 8 machines in sensible configs (1 control, 3 controls, with/withoug ceph, etc.)
- maybe add dockerhub credentials to all microk8s to help avoiding timeouts?
- add proxy support (whatever sunbeam proxy support is at the moment)
- testing
    - ping the initial demo vm, ssh to it and test communication to internet
    - manually create more VMs in admin and demo projects, same test as above
    - run tempest with a test list (from SQA)
- capture evidences
    - most openstack resources (servers, networks, subnets, routers, images, flavors, etc.)
    - terraform status after deployed - this one maybe right after aply finishes?
    - juju status, juju debug-logs?, microceph details, microk8s details, sunbeam logs (SQA has more)
- plugins
    - enable most plugins (they usually time out enabling)
    - test plugins as possible (SQA has some tests already)
- try to pass non-conflicting IPs for simultanous tests
    - although this might not be a problem for single machine tests
    - this is a problem only in maas, equinix has isolated vlans for each group
- try to optimize equinix costs with spot instances