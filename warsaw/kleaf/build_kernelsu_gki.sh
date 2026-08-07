#!/bin/sh
set -eu

if [ "$#" -ne 3 ]; then
    echo "usage: $0 WORKSPACE DIST_DIR MANIFEST" >&2
    exit 2
fi

workspace=$(cd "$1" && pwd)
if [ -e "$2" ] && [ -n "$(find "$2" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]; then
    echo "refusing to reuse non-empty dist directory: $2" >&2
    exit 1
fi
mkdir -p "$2"
dist_dir=$(cd "$2" && pwd)
manifest=$(cd "$(dirname "$3")" && pwd)/$(basename "$3")
output_user_root=${KLEAF_OUTPUT_USER_ROOT:-"$(dirname "$workspace")/bazel-output-jxz-kernelsu"}

if [ "$(uname -s)" != Linux ] || [ "$(uname -m)" != x86_64 ]; then
    echo "KernelSU GKI build requires Linux x86_64" >&2
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
    //warsaw_enhanced:warsaw_gki_kernelsu_dist -- --dist_dir="$dist_dir"

tools/bazel --output_user_root="$output_user_root" build \
    --repo_manifest="$workspace:$manifest" \
    --config=release \
    --jobs=6 \
    --local_resources=cpu=8 \
    --local_resources=memory=10000 \
    //warsaw_enhanced:warsaw_gki_kernelsu_config

config_file=$(tools/bazel --output_user_root="$output_user_root" cquery \
    --repo_manifest="$workspace:$manifest" \
    --config=release \
    --output=files \
    //warsaw_enhanced:warsaw_gki_kernelsu_config | tail -n 1)
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

if [ -n "${WARSAW_OFFICIAL_SYMVERS:-}" ] && [ -n "${WARSAW_STOCK_MODULE_MANIFEST:-}" ]; then
    if [ -f "$WARSAW_OFFICIAL_SYMVERS" ] && [ -f "$WARSAW_STOCK_MODULE_MANIFEST" ]; then
        python3 "$workspace/common/warsaw/kleaf/verify_stock_module_abi.py" \
            --official-symvers="$WARSAW_OFFICIAL_SYMVERS" \
            --candidate-symvers="$dist_dir/vmlinux.symvers" \
            --manifest="$WARSAW_STOCK_MODULE_MANIFEST" \
            --result="$dist_dir/stock-abi-check.json" \
            --mismatches="$dist_dir/stock-abi-mismatches.csv"
    else
        echo "WARSAW_OFFICIAL_SYMVERS or WARSAW_STOCK_MODULE_MANIFEST missing; skipping stock module ABI check" >&2
    fi
fi
