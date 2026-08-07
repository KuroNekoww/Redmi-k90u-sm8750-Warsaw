#!/bin/sh
set -eu

if [ "$#" -ne 4 ]; then
    echo "usage: $0 WORKSPACE KERNEL_TARGET DIST_DIR MANIFEST" >&2
    exit 2
fi

workspace=$(cd "$1" && pwd)
kernel_target=$2
case "$kernel_target" in
    warsaw_gki_*) ;;
    *) echo "invalid enhanced kernel target: $kernel_target" >&2; exit 2 ;;
esac
if [ -e "$3" ] && [ -n "$(find "$3" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]; then
    echo "refusing to reuse non-empty dist directory: $3" >&2
    exit 1
fi
mkdir -p "$3"
dist_dir=$(cd "$3" && pwd)
manifest=$(cd "$(dirname "$4")" && pwd)/$(basename "$4")
output_user_root=${KLEAF_OUTPUT_USER_ROOT:-"$(dirname "$workspace")/bazel-output-$kernel_target"}
package=//warsaw_enhanced

if [ "$(uname -s)" != Linux ] || [ "$(uname -m)" != x86_64 ]; then
    echo "enhanced GKI build requires Linux x86_64" >&2
    exit 1
fi
if [ ! -f "$manifest" ]; then
    echo "manifest does not exist: $manifest" >&2
    exit 1
fi
if [ ! -f "$workspace/common/KernelSU/kernel/Kbuild" ]; then
    echo "ReSukiSU submodule not initialized; run: git -C $workspace/common submodule update --init --recursive" >&2
    exit 1
fi

patch_file="$workspace/common/warsaw/kleaf/patches/resukisu-sm8750.patch"
ksu_src="$workspace/common/KernelSU/kernel"
(
    cd "$workspace/common/KernelSU"
    git checkout -- kernel/Kbuild kernel/policy/app_profile.c
    sed -i "s|^KSU_SRC := .*|KSU_SRC := $ksu_src|" kernel/Kbuild
    git apply "$patch_file"
)

export BUILD_NUMBER=15511674
mkdir -p "$output_user_root"
ulimit -n 65535 2>/dev/null || true
cd "$workspace"

tools/bazel --output_user_root="$output_user_root" run \
    --repo_manifest="$workspace:$manifest" \
    --config=release \
    --jobs=6 \
    --local_resources=cpu=8 \
    --local_resources=memory=10000 \
    "$package:${kernel_target}_dist" -- --dist_dir="$dist_dir"

tools/bazel --output_user_root="$output_user_root" build \
    --repo_manifest="$workspace:$manifest" \
    --config=release \
    --jobs=6 \
    --local_resources=cpu=8 \
    --local_resources=memory=10000 \
    "$package:${kernel_target}_config"

config_file=$(tools/bazel --output_user_root="$output_user_root" cquery \
    --repo_manifest="$workspace:$manifest" \
    --config=release \
    --output=files \
    "$package:${kernel_target}_config" | tail -n 1)
case "$config_file" in
    /*) ;;
    *) config_file="$workspace/$config_file" ;;
esac
if [ -d "$config_file" ]; then
    config_file="$config_file/.config"
fi
if [ ! -f "$config_file" ]; then
    echo "unable to locate generated config: $config_file" >&2
    exit 1
fi

cp "$config_file" "$dist_dir/.config"
printf '%s\n' "$kernel_target" > "$dist_dir/build-target.txt"
