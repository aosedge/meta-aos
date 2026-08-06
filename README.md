# AosCore meta layer

This meta layer contains recipes for AosCore components such as:

* aos-communicationmanager - AosCore communication manager;
* aos-iamanager - AosCore identity and access manager;
* aos-servicemanager - AosCore service manager;
* aos-updatemanager - AosCore update manager;
* aos-vis - AosCore vehicle information service;
* other tools and utility for AosCore operation.

## How to integrate Aos meta layer to custom product

For detailed information how to integrate AosCore to custom product,
see [Aos Core integration](doc/integration.md) document.

## Benchmarking

For the optional CPU/RAM + operation-event monitoring stack (`DISTRO_FEATURES:append = " benchmark"`),
see [AosCore benchmarking](doc/benchmark.md) document.

## Misc

* Set PREFERRED_PROVIDER_virtual/runc = "runc-opencontainers" to build runc from opencontainers.
