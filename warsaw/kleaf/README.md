# Warsaw J-x-Z ReSukiSU GKI

This target derives from the AOSP `android15-6.6-lts` baseline (Linux 6.6.142) while
keeping the workspace and source checkout self-contained.

The first enhancement stage contains only two intentional changes:

1. `CONFIG_LOCALVERSION="-4k-KuroNekoww"` for an unmistakable runtime identity.
2. ReSukiSU built into the GKI, with the Android 6.6 backported seccomp
   release contract handled by `PF_EXITING` via a runtime patch instead of the
   incompatible upstream-version heuristic.

The public branch uses the ReSukiSU git submodule at `common/KernelSU` and
applies `warsaw/kleaf/patches/resukisu-sm8750.patch` at build time.

Container namespaces, optional filesystems, wireless stacks and USB gadget
expansions are intentionally excluded from the public ReSukiSU target.

Any future config expansion must compare every original module `__versions`
entry with the candidate `vmlinux.symvers`. A successful Kleaf/KMI build alone
is not sufficient for a device test.

## Stock module ABI check

The build scripts do not run this check. Kleaf's own KMI check
(`kmi_symbol_list_strict_mode`, `trim_nonlisted_kmi`) runs on every build and
drops `kmi_symbol_list_strict_mode_checked` into the dist dir, but it only
compares against the official GKI symbol baseline in `common/android/`. It does
not prove that this device's stock vendor modules still load.

`verify_stock_module_abi.py` does prove that, by reading each stock module's
`__versions` section and comparing every CRC against the candidate
`vmlinux.symvers`. Run it by hand before any device test, especially for the
`toolbox` and `toolbox_lab` targets:

```sh
python3 warsaw/kleaf/verify_stock_module_abi.py \
    --official-symvers=<official GKI vmlinux.symvers> \
    --candidate-symvers=<dist_dir>/vmlinux.symvers \
    --manifest=<stock module CSV> \
    --result=<dist_dir>/stock-abi-check.json \
    --mismatches=<dist_dir>/stock-abi-mismatches.csv
```

It exits non-zero and sets `device_loading_approved: false` on any mismatch.

Two inputs are device-specific and are not in this repository:

- **official symvers** — the `vmlinux.symvers` from the matching official GKI
  build (`android15-6.6`, build `15511674`), not one produced locally.
- **stock module CSV** — one row per stock module object, with the columns
  `sha256,absolute_path,canonical_module_name,source_class`. `absolute_path`
  must point at a real `.ko` extracted from the device (`/vendor/lib/modules`
  and the vendor_boot / vendor_dlkm images).

The first device test must not combine built-in ReSukiSU with the existing
KernelSU/ReSukiSU LKM in `init_boot`. Prepare and verify an LKM-free `init_boot` rollback
path before authorizing any temporary boot or partition write.

`package_test_boot.py` repacks the locked stock Android boot V4 profile with a
hash-locked candidate `Image`. It permits the kernel payload to grow, while
requiring the empty ramdisk, command line, header version, AArch64 text offset
and flags to remain compatible. Its output is temporary-boot-only.
An explicit `--cmdline` is allowed only for a documented bootstrap image, such
as `kernelsu.allow_shell=1`; the generated report records that intentional
delta.
