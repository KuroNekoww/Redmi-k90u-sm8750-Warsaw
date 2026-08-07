# Building

## Host requirements

- Linux x86-64;
- at least 16 GiB RAM;
- at least 40 GiB free space;
- Git, Python 3, SSH certificates and normal Android kernel build dependencies;
- access to `android.googlesource.com` for the pinned dependency projects.

The build was validated on an Arch-family Linux host. macOS can inspect and
package artifacts but is not a supported Kleaf build host.

## Create the exact workspace

```sh
mkdir warsaw-gki
git clone --recurse-submodules https://github.com/KuroNekoww/Redmi-k90u-sm8750-Warsaw.git \
  warsaw-gki/common
cd warsaw-gki
python3 common/warsaw/sync_workspace.py . --execute
```

The synchronizer prints a plan before making changes, fetches every non-common
project at the exact revision in `manifest_15511674.xml`, installs only the
manifest linkfiles, and links `warsaw_enhanced` to the tracked package in this
repository. It refuses dirty existing projects and unexpected paths.

## Build the validated target

```sh
common/warsaw/kleaf/build_kernelsu_gki.sh \
  "$PWD" \
  "$PWD/out-warsaw-jxz" \
  "$PWD/common/warsaw/manifests/manifest_15511674.xml"
```

The build wrapper forces the official build number `15511674`, uses bounded
host resources and copies the generated `.config` into the output directory.

Expected configuration identity:

```text
CONFIG_LOCALVERSION="-4k-KuroNekoww"
CONFIG_KSU=y
```

## Safety gates

- Build `//warsaw_enhanced:warsaw_gki_kernelsu` only.
- Do not add container namespace/cgroup fragments without a full stock-module
  CRC audit.
- Do not replace DTB, DTBO, vendor_boot, init_boot or hypervisor images.
- Repack only a hash-verified stock Android boot V4 image.
- Use `fastboot boot OUTPUT.img`; do not flash during initial validation.

The repository does not distribute the stock boot image. Supply your own image
from the same device/build and verify it before packaging.
