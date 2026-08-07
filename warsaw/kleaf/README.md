# Warsaw J-x-Z ReSukiSU GKI

This target derives from the runtime-validated exact Warsaw GKI baseline while
keeping the baseline workspace and source checkout untouched.

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
