# Provenance and Attribution

## Authoritative base

| Layer | Revision | Role |
|---|---|---|
| AOSP `kernel/common` | `e56cf6b09cca2151bcee244b3d334fb68685ff57` | Exact source base matching official build 15511674 |
| ReSukiSU | `058cdc931016cb2cb769ed063cce6d65d6df61e0` (submodule) | ReSukiSU kernel driver from `common/KernelSU` |
| Warsaw integration | this branch | Kconfig wiring, ReSukiSU Android 6.6 adaptation, build profile and packaging tools |

The 33-project GKI dependency lock is
`warsaw/manifests/manifest_15511674.xml`. The base source and generated
`vmlinux.symvers` were independently matched to the official Warsaw runtime
evidence before KernelSU was added.

The public branch starts with a source-snapshot root whose tree is byte-for-byte
the tree of AOSP commit `e56cf6b09cca2151bcee244b3d334fb68685ff57`. The exact
local checkout used for reconstruction was intentionally shallow and therefore
could not publish missing parent commits. Full pre-snapshot history remains at
`https://android.googlesource.com/kernel/common`; the `upstream` Git remote points
there. The snapshot-root tree object is
`c701b2cb3998ed7536f97ae358ba8fcf6c75f1f7`.

## Locked integration

- `drivers/Kconfig` SHA-256:
  `d0f5971e085cb288b7440d7a0540a080feef936cb6c62f420192b11918da740a`
- `drivers/Makefile` SHA-256:
  `ae4bf7afcbd8b1c57b02ac5f61cae216e992f2f6471cad9bafa8e400cd8f1006`
- `warsaw/kleaf/patches/resukisu-sm8750.patch` SHA-256:
  (computed at build time)

The ReSukiSU kernel driver lives in the `KernelSU` git submodule. The only
Warsaw-specific adaptation is the runtime patch in
`warsaw/kleaf/patches/resukisu-sm8750.patch`, which adds the
`KSU_SECCOMP_RELEASE_REQUIRES_PF_EXITING` build define and the matching guarded
`PF_EXITING` path in `policy/app_profile.c` for Android 6.6. The `uapi` tree is
provided by the submodule itself; the `drivers/kernelsu` path is a symlink to
`KernelSU/kernel` so the kernel repository stays self-contained.

`workspace_status.json` pins the base AOSP SCM identity and source timestamp so
a clean public commit does not replace the runtime-compatible `ge56cf6b09cca`
identity with the release-documentation commit hash. Product identity is the
explicit `-4k-J-x-Z` config suffix.

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
