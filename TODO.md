
TODO

- matrix of tests
    - find a way to easily test a huge number of combinations (channels/substrates/topologies/etc)
    - (1h1c, 3h1c, 3h3c, 6h3c?) + disaggregated x (storage / no-storage) x (all substrates) / (1 db / many dbs) (all channels)
- testing
    - ping the initial demo vm, ssh to it and test communication to internet
    - manually create more VMs in admin and demo projects, same test as above
    - enable most plugins (they usually time out enabling) - build or test stage?
    - test plugins as possible (SQA has some tests already)
    - run tempest with a test list (from SQA) -- will need various plugins enabled
- try to pass non-conflicting IPs for simultanous clusters tests in maas? (only releant if testing)
- try to optimize equinix costs with spot instances?
- add proxy support (whatever sunbeam proxy support is at the moment)
- Remove escapes/colors/ConsoleNotes from jenkins console log?

+ Migrating equinix substrate to equinix_metal with shared L2 and public gateway
    - how to get allocated ip block in terraform?
