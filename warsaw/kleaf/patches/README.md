# ReSukiSU runtime patches

This directory contains patches that are applied to the ReSukiSU submodule at
build time. The submodule itself (`common/KernelSU`) remains unmodified in the
git index; these patches are re-applied on every Bazel build.

## `resukisu-sm8750.patch`

Adapts ReSukiSU for the Android 6.6 GKI seccomp-release contract used by
Warsaw.

- Adds `-DKSU_SECCOMP_RELEASE_REQUIRES_PF_EXITING=1` to ReSukiSU's `Kbuild`
- Changes the version guard in `kernel/policy/app_profile.c` so `PF_EXITING` is
  set when the build define is present, even on kernel 6.6

This is the same Android 6.6 backport that the previous built-in KernelSU
carried inline; it is now applied as a runtime build patch so the ReSukiSU
submodule can stay on its upstream branch.
