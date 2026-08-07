# Provenance and Attribution

## Authoritative base

| Layer | Revision | Role |
|---|---|---|
| AOSP `kernel/common` | `2c4ce99fdde624f85ae4f01ef5888c3494691210` | Merged `android15-6.6-lts` branch (Linux 6.6.142) |
| ReSukiSU | `058cdc931016cb2cb769ed063cce6d65d6df61e0` (submodule) | ReSukiSU kernel driver from `common/KernelSU` |
| Warsaw integration | this branch | Kconfig wiring, ReSukiSU Android 6.6 adaptation, build profile and packaging tools |

The 33-project GKI dependency lock is
`warsaw/manifests/manifest_15511674.xml`. The base source and generated
`vmlinux.symvers` were independently matched to the official Warsaw runtime
evidence before KernelSU was added.

The Warsaw tree starts from the AOSP `android15-6.6-lts` branch (Linux 6.6.142)
and adds the ReSukiSU submodule and Warsaw-specific build tooling. Full AOSP
history is available upstream at `https://android.googlesource.com/kernel/common`.

## Locked integration

The ReSukiSU kernel driver lives in the `KernelSU` git submodule. The only
Warsaw-specific adaptation is the runtime patch in
`warsaw/kleaf/patches/resukisu-sm8750.patch`, which adds the
`KSU_SECCOMP_RELEASE_REQUIRES_PF_EXITING` build define and the matching guarded
`PF_EXITING` path in `policy/app_profile.c` for Android 6.6. The `uapi` tree is
provided by the submodule itself; the `drivers/kernelsu` path is a symlink to
`KernelSU/kernel` so the kernel repository stays self-contained.

`workspace_status.json` pins the base AOSP SCM identity and source timestamp so
a clean public commit does not replace the runtime-compatible `g2c4ce99fdde6`
identity with the release-documentation commit hash. Product identity is the
explicit `-4k-KuroNekoww` config suffix.

## Attribution policy

The Linux history, copyright notices, SPDX identifiers, license texts and
KernelSU notices are intentionally preserved. J-x-Z authorship applies only to
the Warsaw integration, compatibility work, build tooling and release
documentation. It does not replace the authorship of Linux, AOSP, KernelSU,
Qualcomm, LineageOS, Xiaomi or component-vendor contributors.

Public Qualcomm/Lineage and Xiaomi Annibale trees were used as research and
source-attribution references, but are not vendored here because they are not
the tested Warsaw kernel base. Their exact reference revisions remain recorded
in the private engineering audit and can be cited separately when code is later
ported from them.

## Binary boundary

The public certificate in `warsaw/kleaf/stock-gki-signing-cert.pem` is a
certificate only. It cannot sign code and does not contain Xiaomi's private key.
Stock boot images, modules, firmware and device dumps are not part of this
repository.
