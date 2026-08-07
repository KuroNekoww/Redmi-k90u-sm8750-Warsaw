#!/usr/bin/env python3
"""Synchronize the exact Warsaw GKI dependency workspace without repo."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


COMMON = Path(__file__).resolve().parents[1]
MANIFEST = Path(__file__).resolve().parent / "manifests/manifest_15511674.xml"


def run(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=cwd,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def head(path: Path) -> str:
    return run("git", "rev-parse", "HEAD", cwd=path).stdout.strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_manifest(mirror_prefix: str) -> list[dict[str, object]]:
    root = ET.parse(MANIFEST).getroot()
    remotes = {
        remote.attrib["name"]: remote.attrib["fetch"]
        for remote in root.findall("remote")
    }
    default = root.find("default")
    default_remote = default.attrib.get("remote", "") if default is not None else ""
    default_revision = default.attrib.get("revision", "") if default is not None else ""
    projects = []
    for project in root.findall("project"):
        remote_name = project.attrib.get("remote", default_remote)
        revision = project.attrib.get("revision", default_revision)
        upstream = f"{remotes[remote_name].rstrip('/')}/{project.attrib['name']}"
        fetch = (
            f"{mirror_prefix.rstrip('/')}/{project.attrib['name']}"
            if mirror_prefix
            else upstream
        )
        projects.append(
            {
                "path": project.attrib["path"],
                "name": project.attrib["name"],
                "revision": revision,
                "fetch": fetch,
                "upstream": upstream,
                "depth": int(project.attrib.get("clone-depth", "1")),
                "linkfiles": [dict(item.attrib) for item in project.findall("linkfile")],
            }
        )
    return projects


def ensure_common(workspace: Path) -> None:
    target = workspace / "common"
    if target.exists() or target.is_symlink():
        if target.resolve() != COMMON:
            raise SystemExit(f"workspace common points elsewhere: {target}")
    else:
        target.symlink_to(COMMON, target_is_directory=True)
    status = run(
        "git", "status", "--porcelain=v1", "--untracked-files=all", cwd=COMMON
    ).stdout
    if status:
        raise SystemExit("refusing a dirty Warsaw common repository")


def ensure_kernelsu_symlink(common_dir: Path) -> None:
    """Ensure drivers/kernelsu is a symlink to the ReSukiSU submodule.

    The ReSukiSU submodule is expected to be populated during the initial
    ``git clone --recurse-submodules``; this helper only recreates the symlink
    if it is missing or points elsewhere.
    """
    symlink = common_dir / "drivers" / "kernelsu"
    target = Path("../KernelSU/kernel")
    if symlink.is_symlink() and Path(os.readlink(symlink)) == target:
        return
    if symlink.exists():
        raise SystemExit(f"drivers/kernelsu is not the expected symlink: {symlink}")
    symlink.symlink_to(target, target_is_directory=True)


def sync_project(workspace: Path, project: dict[str, object]) -> None:
    target = workspace / str(project["path"])
    revision = str(project["revision"])
    if target.exists() or target.is_symlink():
        if not (target / ".git").exists():
            raise SystemExit(f"existing path is not a Git worktree: {target}")
        status = run(
            "git", "status", "--porcelain=v1", "--untracked-files=all", cwd=target
        ).stdout
        if status:
            raise SystemExit(f"refusing dirty dependency: {target}")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        run("git", "init", str(target))
        run("git", "remote", "add", "origin", str(project["fetch"]), cwd=target)

    run("git", "remote", "set-url", "origin", str(project["fetch"]), cwd=target)
    current = run("git", "rev-parse", "HEAD", cwd=target, check=False)
    if current.returncode == 0 and current.stdout.strip() == revision:
        print(f"READY {project['path']} {revision}", flush=True)
        return
    print(f"SYNC  {project['path']} {revision}", flush=True)
    run(
        "git",
        "fetch",
        "--depth",
        str(project["depth"]),
        "origin",
        revision,
        cwd=target,
    )
    run("git", "checkout", "--detach", "FETCH_HEAD", cwd=target)
    if head(target) != revision:
        raise SystemExit(f"revision mismatch after sync: {target}")


def install_links(workspace: Path, projects: list[dict[str, object]]) -> None:
    for project in projects:
        source_root = workspace / str(project["path"])
        for item in project["linkfiles"]:
            source = source_root / item["src"]
            destination = workspace / item["dest"]
            expected = Path(os.path.relpath(source, destination.parent))
            if destination.is_symlink() and Path(os.readlink(destination)) == expected:
                continue
            if destination.exists() or destination.is_symlink():
                raise SystemExit(f"refusing existing linkfile destination: {destination}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.symlink_to(expected)

    package = workspace / "warsaw_enhanced"
    expected_package = Path("common/warsaw/kleaf")
    if package.is_symlink() and Path(os.readlink(package)) == expected_package:
        return
    if package.exists() or package.is_symlink():
        raise SystemExit(f"refusing existing Warsaw package path: {package}")
    package.symlink_to(expected_package, target_is_directory=True)


def write_lock(workspace: Path, projects: list[dict[str, object]]) -> None:
    records = [{"path": "common", "head": head(COMMON), "source": "this repository"}]
    for project in projects:
        if project["path"] == "common":
            continue
        records.append(
            {
                "path": project["path"],
                "head": head(workspace / str(project["path"])),
                "upstream": project["upstream"],
                "fetch": project["fetch"],
            }
        )
    data = {
        "manifest": str(MANIFEST),
        "manifest_sha256": sha256(MANIFEST),
        "projects": records,
    }
    (workspace / "warsaw-gki-workspace-lock.json").write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--mirror-prefix", default="")
    parser.add_argument("--minimum-free-gib", type=int, default=25)
    args = parser.parse_args()

    workspace = args.workspace.expanduser().resolve()
    projects = parse_manifest(args.mirror_prefix)
    plan = {
        "workspace": str(workspace),
        "manifest": str(MANIFEST),
        "project_count": len(projects),
        "projects": [
            {key: project[key] for key in ("path", "revision", "fetch")}
            for project in projects
        ],
    }
    print(json.dumps(plan, indent=2, sort_keys=True))
    if not args.execute:
        print("PLAN ONLY: pass --execute to synchronize", file=sys.stderr)
        return

    workspace.mkdir(parents=True, exist_ok=True)
    ensure_common(workspace)
    ensure_kernelsu_symlink(COMMON)
    for project in projects:
        if project["path"] == "common":
            continue
        free_gib = shutil.disk_usage(workspace).free // (1024**3)
        if free_gib < args.minimum_free_gib:
            raise SystemExit(
                f"disk guard stopped at {free_gib} GiB before {project['path']}"
            )
        sync_project(workspace, project)
    install_links(workspace, projects)
    write_lock(workspace, projects)
    print(f"SYNC COMPLETE: {workspace}")


if __name__ == "__main__":
    main()
