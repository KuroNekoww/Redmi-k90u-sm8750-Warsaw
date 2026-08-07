# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

Android 15 GKI 6.6 kernel (Linux 6.6.118) for the Xiaomi Redmi K90 Ultra (`warsaw`) engineering device with SM8750 SoC. It is a hybrid kernel source: the exact AOSP `kernel/common` tree at commit `e56cf6b09cca` plus ReSukiSU built-in and Warsaw-specific build tooling. The branch `warsaw-android15-6.6` is the main/only branch.

**Important constraint**: This is not a full OEM drop. Stock DTB, DTBO, vendor modules, and firmware are authoritative and NOT replaced by this tree. Never modify scheduler data structures or GKI symbol CRCs — it would break the stock-module ABI.

## Repository layout

```
common/                         # This repo (checked out as "common" inside workspace)
├── KernelSU/                   # ReSukiSU git submodule (common/KernelSU/kernel is symlinked as drivers/kernelsu)
├── drivers/
│   └── kernelsu -> ../KernelSU/kernel  # symlink to ReSukiSU driver source
├── warsaw/                     # All Warsaw-specific additions
│   ├── kleaf/                  # Kleaf (Bazel) build targets and config fragments
│   │   ├── BUILD.bazel         # Build targets: warsaw_gki_kernelsu, warsaw_gki_toolbox, warsaw_gki_toolbox_lab
│   │   ├── targets.bzl         # warsaw_kernel() macro wrapping kernel_build + copy_to_dist_dir
│   │   ├── build_kernelsu_gki.sh  # Primary build entry point
│   │   ├── package_test_boot.py    # Repacks stock boot.img with candidate kernel Image
│   │   ├── patches/             # Runtime patches applied before Bazel build
│   │   └── jxz-*.fragment       # Kconfig fragments (kernelsu, toolbox, toolbox-lab)
│   ├── manifests/              # GKI dependency lock manifests (manifest_15511674.xml)
│   └── sync_workspace.py       # Workspace setup: clones pinned deps from android.googlesource.com
├── build.config.*              # Android kernel build config fragments
├── BUILD.bazel                 # Top-level Bazel build (kernel_aarch64_sources, etc.)
├── modules.bzl                 # GKI module lists (get_gki_modules_list, get_kunit_modules_list)
└── workspace_status.json       # Pins SCMVERSION and SOURCE_DATE_EPOCH for reproducible builds
```

The expected workspace layout (created by `sync_workspace.py`) is:
```
warsaw-gki/
├── common/                     # This repo
├── warsaw_enhanced/            # Symlink to common/warsaw (created by sync)
├── bazel-output-jxz-kernelsu/  # Bazel output cache
├── out-warsaw-jxz/             # Build artifacts (dist_dir)
└── prebuilts/, build/, kernel/, toolchain/  # Fetched from AOSP
```

## Build system: Kleaf (Bazel)

This kernel uses **Kleaf**, Android's Bazel-based kernel build system. The build orchestrator is `tools/bazel` (a Bazel wrapper).

### Build commands

**Full workspace setup + build:**
```sh
mkdir warsaw-gki && cd warsaw-gki
git clone --recurse-submodules <this-repo> common
python3 common/warsaw/sync_workspace.py . --execute
common/warsaw/kleaf/build_kernelsu_gki.sh "$PWD" "$PWD/out-warsaw-jxz" "$PWD/common/warsaw/manifests/manifest_15511674.xml"
```

**Build only (after workspace is set up):**
```sh
# Primary target: ReSukiSU-enabled GKI
tools/bazel --output_user_root=<bazel_cache_dir> run \
    --repo_manifest=<workspace>:<manifest> \
    --config=release \
    //warsaw_enhanced:warsaw_gki_kernelsu_dist -- --dist_dir=<output_dir>
```

**Other build targets** (defined in `warsaw/kleaf/BUILD.bazel`):
- `//warsaw_enhanced:warsaw_gki_kernelsu` — ReSukiSU only
- `//warsaw_enhanced:warsaw_gki_toolbox` — ReSukiSU + common modules (btusb, vxlan, ntfs3, squashfs, etc.)
- `//warsaw_enhanced:warsaw_gki_toolbox_lab` — toolbox + lab modules (nbd, bonding, usbip, isofs, udf, pktgen)

**Config-only build:**
```sh
tools/bazel build //warsaw_enhanced:warsaw_gki_kernelsu_config
```

### Build constraints
- Host must be **Linux x86_64** (validated on Arch-family)
- At least 16 GiB RAM, 40 GiB free disk
- Bazel resource limits: `--jobs=6 --local_resources=cpu=8 --local_resources=memory=10000`
- The build wrapper forces `BUILD_NUMBER=15511674` for reproducibility

## Verification and testing

There are no traditional unit tests. Manual verification steps:

```sh
# Repack boot image for fastboot test (no flashing)
python3 warsaw/kleaf/package_test_boot.py --stock-boot <stock.img> --kernel-image <Image> --out <test_boot.img>
```

**Device testing**: Only use `fastboot boot <test_boot.img>`. Never flash both bootable slots during early validation. Keep known-good boot and init_boot images available.

## Patch requirements

All patches must follow Android Common Kernel conventions:
- Pass `scripts/checkpatch.pl`
- Must not break `gki_defconfig` or `allmodconfig` for arm/arm64/x86/x86_64
- Subject tags: `ANDROID:`, `UPSTREAM:`, `BACKPORT:`, `FROMGIT:`, or `FROMLIST:`
- Must include `Change-Id:` and `Signed-off-by:` tags
- Warsaw-specific patches use the `ANDROID: warsaw:` prefix (see `git log --oneline`)

## Key invariants (do not violate)

1. **Never change GKI symbol CRCs** without a full stock-module ABI audit
2. **Never replace DTB, DTBO, vendor_boot, init_boot, or hypervisor images** — stock partitions are authoritative
3. **Do not add container namespace/cgroup fragments** without a full stock-module CRC audit
4. **Stock vendor modules and firmware are authoritative**
5. **`workspace_status.json` pins SCM identity** — do not change it casually; product identity is in `CONFIG_LOCALVERSION` instead

## Kernel configuration

Configuration is layered through Kconfig fragments in `warsaw/kleaf/`:
- `jxz-kernelsu.fragment` — enables `CONFIG_KSU=y`, sets `CONFIG_LOCALVERSION="-4k-KuroNekoww"`
- `jxz-toolbox.fragment` — enables additional modules (btusb, vxlan, ntfs3, squashfs, netlink_diag, etc.)
- `jxz-toolbox-lab.fragment` — enables lab-oriented modules (nbd, bonding, usbip, isofs, udf, pktgen)

Expected runtime version string: `6.6.118-android15-8-ge56cf6b09cca-ab15511674-4k-KuroNekoww`

## ReSukiSU notes

- ReSukiSU is built **into** the GKI kernel (not as an LKM)
- The stock init_boot may contain an older KernelSU/ReSukiSU LKM — prepare an LKM-free `init_boot` rollback before testing
- The `PF_EXITING` seccomp-release compatibility fix is applied as a runtime patch (`warsaw/kleaf/patches/resukisu-sm8750.patch`) before every Bazel build
