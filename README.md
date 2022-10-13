# Aos meta layer

This meta layer contains recipes for Aos components such as:

* aos-communicationmanager - Aos communication manager;
* aos-iamanager - Aos identity and access manager;
* aos-servicemanager - Aos service manager;
* aos-updatemanager - Aos update manager;
* aos-vis - Aos vehicle information service;
* Aos CNI plugins;
* other tools and utility for AosEdge core part.

## How to integrate Aos meta layer to custom product

For detailed information how to integrate AosCore to custom product,
see [Aos Core integration](doc/integration.md) document.

## Misc

* Set PREFERRED_PROVIDER_virtual/runc = "runc-opencontainers" to build runc from opencontainers.
* Set AOS_RUNNER to define which runner will be used to run Aos services. Currently supported: runc and crun.
Default is crun.
