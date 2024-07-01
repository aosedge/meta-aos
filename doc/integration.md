# AosCore integration

## Prerequisite

* meta-aos was verified and tested on Yocto 4.0 (Kirkstone) and 3.1 (Dunfell);
* required additional meta layers: meta-virtualization, meta-security;
* init manager: systemd;
* required distro features: virtualization, seccomp;
* kernel options (modules or builtin): bridge, nf_conncount, nfnetlink, overlay, squashfs, veth, xt_addrtype,
xt_comment, xt_conntrack, xt_masquerade
* dedicated RW partition to store Aos services, layers and OTA update artifacts.

## Main components integration

The custom build should satisfy the above requirements in order to integrate main Aos components. The requirements can
be configured or implemented in different ways. The following steps shows one of possible way how to configure the
custom build to have Aos main components integrated.

Required meta layers should be added to `bblayers.conf` file. The basic meta layers configuration should look like:

```bash
BBLAYERS ?= " \
    ${TOPDIR}/../poky/meta \
    ${TOPDIR}/../poky/meta-poky \
    ${TOPDIR}/../poky/meta-yocto-bsp \
    ${TOPDIR}/../meta-aos \
    ${TOPDIR}/../meta-virtualization \
    ${TOPDIR}/../meta-security \
    ${TOPDIR}/../meta-openembedded/meta-oe \
    ${TOPDIR}/../meta-openembedded/meta-filesystems \
    ${TOPDIR}/../meta-openembedded/meta-python \
    ${TOPDIR}/../meta-openembedded/meta-perl \
    ${TOPDIR}/../meta-openembedded/meta-networking \
  "
```

Systemd should be set as system init manager:

```bash
INIT_MANAGER = "systemd"
```

Virtualization and security distro features should be enabled in `local.conf`:

```bash
DISTRO_FEATURES:append = " virtualization security"
```

The required kernel options should be enabled in kernel config as modules or builtin. See [Yocto Project Linux Kernel
Development Manual](https://docs.yoctoproject.org/kernel-dev/index.html) for details.

Aos service instances use the host rootfs as base layer for its containerized rootfs. Due to overlay mount
implementation, the services and layers rootfs should be stored on a separate from host rootfs partition. By default,
Aos services and layers are stored on /var/aos folder. Thus, the separate partition should be mounted on /var or
/var/aos folder. It could be done using Yocto wks plugin. Add the separate var partition into `custom.wks.in` file:

```bash
# short-description: Create an EFI disk image for genericx86*
# long-description: Creates a partitioned EFI disk image for genericx86* machines
part /boot --source bootimg-efi --sourceparams="loader=${EFI_PROVIDER}" --ondisk hda --label msdos --active --align 1024
part / --source rootfs --ondisk hda --fstype=ext4 --label root --align 1024 --use-uuid
part /var --source rootfs --rootfs-dir=${IMAGE_ROOTFS} --ondisk hda --fstype=ext4 --label var --align 1024 --size 512M --change-directory ./var
part swap --ondisk hda --size 44 --label swap1 --fstype=swap

bootloader --ptable gpt --timeout=5 --append="rootfstype=ext4 console=ttyS0,115200 console=tty0"
```

Custom wks file should be located in `wic` folder and set in `local.conf`:

```bash
WKS_FILE = "custom.wks.in"
```

Aos main components should be added into the target image by appending `IMAGE_INSTALL` variable in `local.conf`:

```bash
IMAGE_INSTALL:append = " aos-iamanager aos-provfirewall aos-communicationmanager aos-servicemanager aos-updatemanager"
```

`aos-iamanager`, `aos-communicationmanager`, `aos-servicemanager` are core Aos components. `aos-updatemanager` is
responsible for Aos OTA updates. If OTA system components update is not needed, `aos-updatemanager` may be removed from
the target image. It also required `umController` section to be removed from `aos-communicationmanager` config as
well as `um` storage to be removed from `aos-iamanager` config. `aos-provfirewall` is helper service that closes
provisioning ports after provisioning for security reason.

Once flashed, the custom board is ready to be provisioned. See
[Get started](https://docs.aosedge.tech/docs/quick-start/) cookbook, to provision and work with Aos
Edge.

## Using secure keys and certificates modules

Keys and certificates are used to create secure connection between Aos components as well as perform secure services and
firmware OTA updates. These keys and certificates are created by `aos-iamanager` during provisioning procedure.
By default, these items are stored in raw format on the file system. It is done for example only and not recommended for
production usage.

`aos-iamanager` supports different secure modules ([TPM](https://en.wikipedia.org/wiki/Trusted_Platform_Module),
[PKCS11](http://docs.oasis-open.org/pkcs11/pkcs11-base/v2.40/os/pkcs11-base-v2.40-os.html)) recommended for production.

[aos-vm][aos-vm] product uses [softhsm](https://www.opendnssec.org/softhsm/)
implementation as reference example how to configure PKCS11 secure module in `aos-iamanager`. See this product
`aos-iamanager` configuration for more details.

[aos-rcar-gen3][aos-rcar-gen3] and [aos-rcar-gen4][aos-rcar-gen4] products use
[OP-TEE](https://optee.readthedocs.io/en/latest/) PKCS11 implementation. It can be used as reference for ARM based
custom boards. See this product `aos-iamanager` configuration for more details.

## Aos disk encryption

Aos services and layers are stored in raw format on the dedicated Aos partition. These data can be exposed. It is
recommended to encrypt Aos dedicated partition. It can be done with any appropriate tool: cryptsetup,
systemd-cryptsetup, etc.

However, `meta-aos` provide own implementation for disk encryption and disk opening. `meta-aos` uses
[diskencryption](https://github.com/aosedge/meta-aos/tree/main/recipes-crypto/diskencryption) script. This script is
called by `aos-iamanager` during provisioning to encrypt disk and used by Aos `initramfs` to open the disk. Although
the disk can be opened by the init manager, in Aos example products it is opened in Aos `initramfs` because it is
required by Aos update reference implementation. See `aos-iamanager` and `initramfs` configurations in
[aos-vm][aos-vm], [aos-rcar-gen3][aos-rcar-gen3] and [aos-rcar-gen4][aos-rcar-gen4] reference products.

Aos disk encryption required empty partition to be present in the image. During provisioning, `aos-iamanager` encrypts
this partition and creates required logical disks on this partition using `aos-setupdisk` recipe. The encrypted
partition is being opened in Aos initramfs on startup using dedicated (`opendisk`) initramfs script. This script should
be included in the Aos initramfs and properly configure with dedicated initramfs command line options. See `opendisk`
script implementation in `initramfs-framework` recipe.

## Aos initramfs

Aos initramfs implements different Aos system functionalities such as opening encrypted Aos partition, update rootfs
using `overlayfs` approach etc. In order to use these functionality, the Aos initramfs should be enabled in the build by
setting the following variables in `local.conf`:

```bash
INITRAMFS_IMAGE = "aos-image-initramfs"
INITRAMFS_IMAGE_BUNDLE = "0"
INITRAMFS_FSTYPES = "cpio.gz"
```

It consists of different Aos initramfs scripts locate in `initramfs-framework` recipe. Selection of the required scripts
could be done by customizing `aos-image-initramfs` recipe. These script should be properly configured using initramfs
command line option. The options are described in the corresponding script implementation. See [aos-vm][aos-vm],
[aos-rcar-gen3][aos-rcar-gen3] and [aos-rcar-gen4][aos-rcar-gen4] reference products.

## Enable SELinux (optional)

Optionally SELinux can be enabled by adding the following configuration:

```bash
DISTRO_FEATURES:append = " acl xattr pam selinux"
```

If enabled, you would, probably, need to adjust SELinux policy according to your build requirements.
The used policy is hosted in [refpolicy][refpolicy] repo.

## Integrate Aos VIS (optional)

Aos VIS is Aos implementation of W3C [Vehicle Information Service](https://www.w3.org/TR/vehicle-information-service/).
VIS is intended to provide vehicle data to the user services as well as provide unit identification information. Such
as system ID, board model, current subjects etc.

Aos VIS with default configuration can be added into the target system by appending `IMAGE_INSTALL` variable in
`local.conf`:

```bash
IMAGE_INSTALL:append = " aos-vis"
```

In order to get unit identification from VIS, `visidentifier` plugin should be set in aos-iamanger and aos-iamanger
should be configured accordingly. See `aos-iamanager` configuration in [aos-vm][aos-vm] product.

## Create layers

Aos layers are shared file system layers that used by Aos services. Aos layers are mounted with overlayfs over local
service rootfs. `meta-aos` contains `layer-generator` bbclass that generate Aos layers. As Aos core uses the host
rootfs as base layer, it is required to create a virtual base layer that duplicate the origin rootfs and that is used
by other layer recipes. See [aos-vm][aos-vm] layers as example.

## Integrate Aos FOTA update

`aos-updatemanager` performs Aos OTA update of different system components with dedicated plugins. `aos-updatemanager`
has an example implementation of updating disk partitions using dual partition (A/B) approach as well as using overlay
approach. Aos overlay OTA update supports incremental update (delta update) whereas dual partition update supports only
full partition update.

See reference Aos products as example of boot and roofs partitions update. At these products, rootfs is updated using
overlay approach, boot partition is updated using A/B approach. In [aos-vm][aos-vm] switching between A/B partition is
done by using `efi` boot manager at same time in [aos-rcar-gen3][aos-rcar-gen3] and [aos-rcar-gen4][aos-rcar-gen4]
switching A/B partition is done by using U-Boot environment variables.

For a custom component update, the appropriate `aos-updatemanager` shall be implemented and integrated.

Reference Aos FOTA implementation requires readonly rootfs. It can be enabled by setting the following variable in
`local.conf`:

```bash
IMAGE_FEATURES:append = " read-only-rootfs"
```

`meta-aos` provides base Aos image recipe with RO rootfs and generating required for FOTA versioning files. You can
simple use it as your image file or include it in your own image file:

```bash
require recipes-core/images/aos-image.inc
```

See [aos-vm][aos-vm] for reference.

## Integration using moulin meta build system

Please see  moulin documentation [moulin][moulin] for getting information about `moulin` build system.

In the case of the usage of the moulin, part of the previously described steps should be put into the YAML file as shown
below. Pay attention, part of the changes should be implemented inside Yocto's recipes.

Example of the YAML file with options required to integrate AOS components into the custom build (`bsp_name`):

```yaml
variables:
  YOCTOS_WORK_DIR: "yocto"
  BSP_BUILD_DIR: "build_bsp"

components:
  bsp_name:
    build-dir: "%{YOCTOS_WORK_DIR}"
    default: true
    sources:
      # list required repos with revisions
      # ...
    builder:
      type: yocto
      work_dir: "%{BSP_BUILD_DIR}"
      conf:
        # Initramfs configuration
        - [INITRAMFS_IMAGE, "aos-image-initramfs"]
        - [INITRAMFS_IMAGE_BUNDLE, "0"]
        - [INITRAMFS_FSTYPES, "cpio.gz"]
        - [INIT_MANAGER, "systemd"]
        - [DISTRO_FEATURES:append, " virtualization security"]
        # selinux is optional
        - [DISTRO_FEATURES:append, " acl xattr pam selinux"]
        - [IMAGE_INSTALL:append, " aos-iamanager aos-provfirewall aos-communicationmanager aos-servicemanager aos-updatemanager"]
        # AOS VIS is optional
        - [IMAGE_INSTALL:append, " aos-vis"]
        # AOS FOTA specific option
        - [IMAGE_FEATURES:append, " read-only-rootfs"]

        # add other variables if required
        # ...

      layers:
        - "../poky/meta"
        - "../poky/meta-poky"
        - "../poky/meta-yocto-bsp"
        - "../meta-aos"
        - "../meta-virtualization"
        - "../meta-security"
        - "../meta-openembedded/meta-oe"
        - "../meta-openembedded/meta-filesystems"
        - "../meta-openembedded/meta-python"
        - "../meta-openembedded/meta-perl"
        - "../meta-openembedded/meta-networking"
        # add other required layers
        # ...

images:
  full:
    type: gpt
    desc: "Aos full image"
    partitions:
      boot:
        gpt_type: 21686148-6449-6E6F-744E-656564454649 # BIOS boot partition (kinda...)
        type: vfat
        size: 256 MiB
        items:
          # add your boot items
          # ...

      rootfs:
        gpt_type: B921B045-1DF0-41C3-AF44-4C6F280D3FAE # Linux aarch64 root
        type: raw_image
        image_path: "%{YOCTOS_WORK_DIR}/build-%{NODE_ID}/tmp/deploy/images/%{MACHINE}/aos-vm-%{NODE_ID}-%{MACHINE}.ext4"

      aos:
        gpt_type: CA7D7CCB-63ED-4C53-861C-1742536059CC # LUKS partition
        type: empty
        size: 2048 MiB
```

[aos-vm]: https://github.com/aosedge/meta-aos-vm
[aos-rcar-gen3]: https://github.com/aosedge/meta-aos-rcar-gen3
[aos-rcar-gen4]: https://github.com/aosedge/meta-aos-rcar-gen4
[refpolicy]: https://github.com/aosedge/refpolicy
[moulin]: https://moulin.readthedocs.io/en/latest/
