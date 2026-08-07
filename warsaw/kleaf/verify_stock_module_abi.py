#!/usr/bin/env python3

import argparse
import csv
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_symvers(path: Path) -> dict[str, int]:
    result = {}
    for line in path.read_text(errors="replace").splitlines():
        parts = line.split()
        if len(parts) >= 2:
            result[parts[1]] = int(parts[0], 16)
    return result


def elf_sections(path: Path) -> tuple[bytes, str, dict[str, tuple[int, int]]]:
    data = path.read_bytes()
    if len(data) < 64 or data[:4] != b"\x7fELF" or data[4] != 2:
        raise ValueError("not ELFCLASS64")
    endian = "<" if data[5] == 1 else ">" if data[5] == 2 else ""
    if not endian:
        raise ValueError("invalid ELF byte order")
    elf_type, machine = struct.unpack_from(endian + "HH", data, 16)
    if elf_type != 1 or machine != 183:
        raise ValueError("not AArch64 ET_REL")
    section_offset = struct.unpack_from(endian + "Q", data, 40)[0]
    entry_size, count, names_index = struct.unpack_from(endian + "HHH", data, 58)
    if entry_size < 64 or section_offset + entry_size > len(data):
        raise ValueError("invalid section table")
    first = struct.unpack_from(endian + "IIQQQQIIQQ", data, section_offset)
    if count == 0:
        count = first[5]
    if names_index == 0xFFFF:
        names_index = first[6]
    if count <= 0 or section_offset + count * entry_size > len(data):
        raise ValueError("section table exceeds file")
    raw_sections = []
    for index in range(count):
        values = struct.unpack_from(
            endian + "IIQQQQIIQQ", data, section_offset + index * entry_size
        )
        raw_sections.append((values[0], values[4], values[5], values[1]))
    if not 0 <= names_index < len(raw_sections):
        raise ValueError("invalid section-name table")
    _, names_offset, names_size, _ = raw_sections[names_index]
    names = data[names_offset : names_offset + names_size]
    sections = {}
    for name_offset, offset, size, section_type in raw_sections:
        if name_offset >= len(names):
            raise ValueError("section name exceeds string table")
        end = names.find(b"\0", name_offset)
        if end < 0:
            raise ValueError("unterminated section name")
        name = names[name_offset:end].decode("utf-8", "replace")
        if section_type != 8 and offset + size > len(data):
            raise ValueError(f"section exceeds file: {name}")
        sections[name] = (offset, size)
    return data, endian, sections


def module_versions(data: bytes, endian: str, sections: dict[str, tuple[int, int]]) -> dict[str, int]:
    section = sections.get("__versions")
    if section is None:
        return {}
    offset, size = section
    raw = data[offset : offset + size]
    if len(raw) % 64:
        raise ValueError("invalid __versions record size")
    result = {}
    for record_offset in range(0, len(raw), 64):
        crc = struct.unpack_from(endian + "Q", raw, record_offset)[0]
        name = raw[record_offset + 8 : record_offset + 64].split(b"\0", 1)[0]
        result[name.decode("utf-8", "replace")] = crc
    return result


def module_exports(data: bytes, sections: dict[str, tuple[int, int]]) -> set[str]:
    result = set()
    for section_name in ("__ksymtab_strings", "___ksymtab_strings"):
        section = sections.get(section_name)
        if section is None:
            continue
        offset, size = section
        for value in data[offset : offset + size].split(b"\0"):
            if value:
                result.add(value.decode("utf-8", "replace"))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--official-symvers", required=True, type=Path)
    parser.add_argument("--candidate-symvers", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--mismatches", required=True, type=Path)
    args = parser.parse_args()

    manifest = args.manifest.expanduser().resolve()
    official_path = args.official_symvers.expanduser().resolve()
    candidate_path = args.candidate_symvers.expanduser().resolve()
    official = load_symvers(official_path)
    candidate = load_symvers(candidate_path)

    with manifest.open(newline="") as stream:
        occurrences = list(csv.DictReader(stream))
    unique_objects = {}
    for row in occurrences:
        unique_objects.setdefault(row["sha256"], row)

    missing_files = []
    parse_failures = []
    original_crc_anomalies = []
    mismatch_rows = []
    shadow_references = []
    exported_names = {}
    affected_objects = Counter()
    affected_names = set()
    mismatch_symbols = Counter()

    candidate_added = set(candidate) - set(official)
    for object_sha256, row in sorted(unique_objects.items()):
        path = Path(row["absolute_path"])
        module_name = row["canonical_module_name"]
        if not path.is_file():
            missing_files.append(str(path))
            continue
        try:
            data, endian, sections = elf_sections(path)
            versions = module_versions(data, endian, sections)
            exports = module_exports(data, sections)
        except (OSError, ValueError, struct.error) as error:
            parse_failures.append(
                {"module": module_name, "path": str(path), "error": str(error)}
            )
            continue
        for symbol in exports & candidate_added:
            exported_names.setdefault(symbol, []).append(module_name)
        object_mismatch_count = 0
        for symbol, module_crc in sorted(versions.items()):
            if symbol in official and official[symbol] != module_crc:
                original_crc_anomalies.append(
                    {
                        "module": module_name,
                        "symbol": symbol,
                        "module_crc": f"0x{module_crc:08x}",
                        "official_crc": f"0x{official[symbol]:08x}",
                    }
                )
            if symbol in official and candidate.get(symbol) != module_crc:
                object_mismatch_count += 1
                mismatch_symbols[symbol] += 1
                mismatch_rows.append(
                    {
                        "module": module_name,
                        "object_sha256": object_sha256,
                        "source_class": row["source_class"],
                        "path": str(path),
                        "symbol": symbol,
                        "module_crc": f"0x{module_crc:08x}",
                        "official_crc": f"0x{official[symbol]:08x}",
                        "candidate_crc": (
                            f"0x{candidate[symbol]:08x}"
                            if symbol in candidate
                            else "MISSING"
                        ),
                    }
                )
            elif symbol in candidate_added:
                shadow_references.append(
                    {
                        "module": module_name,
                        "symbol": symbol,
                        "module_crc": f"0x{module_crc:08x}",
                        "candidate_crc": f"0x{candidate[symbol]:08x}",
                    }
                )
        if object_mismatch_count:
            affected_objects[module_name] = max(
                affected_objects[module_name], object_mismatch_count
            )
            affected_names.add(module_name)

    official_missing = sorted(set(official) - set(candidate))
    official_changed = sorted(
        symbol
        for symbol in set(official) & set(candidate)
        if official[symbol] != candidate[symbol]
    )
    export_collisions = [
        {"symbol": symbol, "modules": sorted(modules)}
        for symbol, modules in sorted(exported_names.items())
    ]
    pass_condition = not any(
        (
            missing_files,
            parse_failures,
            original_crc_anomalies,
            mismatch_rows,
            shadow_references,
            export_collisions,
            official_missing,
            official_changed,
        )
    )

    result = {
        "schema_version": 1,
        "status": "PASS" if pass_condition else "FAIL",
        "scope": "Compatibility of stock Warsaw module objects with a candidate GKI vmlinux.symvers",
        "inputs": {
            "manifest": str(manifest),
            "manifest_sha256": sha256(manifest),
            "official_symvers": str(official_path),
            "official_symvers_sha256": sha256(official_path),
            "candidate_symvers": str(candidate_path),
            "candidate_symvers_sha256": sha256(candidate_path),
        },
        "counts": {
            "occurrences": len(occurrences),
            "unique_module_objects": len(unique_objects),
            "missing_module_files": len(missing_files),
            "parse_failures": len(parse_failures),
            "official_kernel_symbols": len(official),
            "candidate_kernel_symbols": len(candidate),
            "official_symbols_missing_from_candidate": len(official_missing),
            "official_symbols_with_changed_crc": len(official_changed),
            "candidate_added_symbols": len(candidate_added),
            "original_module_crc_anomalies": len(original_crc_anomalies),
            "affected_unique_module_objects": len(
                {row["object_sha256"] for row in mismatch_rows}
            ),
            "affected_canonical_module_names": len(affected_names),
            "incompatible_module_symbol_pairs": len(mismatch_rows),
            "distinct_incompatible_kernel_symbols": len(mismatch_symbols),
            "candidate_added_symbol_references": len(shadow_references),
            "candidate_added_export_collisions": len(export_collisions),
        },
        "candidate_added_symbols": sorted(candidate_added),
        "official_symbols_missing_from_candidate": official_missing,
        "official_symbols_with_changed_crc_sample": official_changed[:100],
        "top_affected_modules": [
            {"module": module, "mismatch_count": count}
            for module, count in affected_objects.most_common(50)
        ],
        "top_incompatible_symbols": [
            {"symbol": symbol, "affected_object_count": count}
            for symbol, count in mismatch_symbols.most_common(100)
        ],
        "missing_module_files": missing_files,
        "parse_failures": parse_failures,
        "original_module_crc_anomalies": original_crc_anomalies[:100],
        "candidate_added_symbol_references": shadow_references[:100],
        "candidate_added_export_collisions": export_collisions,
        "device_loading_approved": pass_condition,
    }

    result_path = args.result.expanduser().resolve()
    mismatch_path = args.mismatches.expanduser().resolve()
    result_path.parent.mkdir(parents=True, exist_ok=True)
    mismatch_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    fieldnames = [
        "module",
        "object_sha256",
        "source_class",
        "path",
        "symbol",
        "module_crc",
        "official_crc",
        "candidate_crc",
    ]
    with mismatch_path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(mismatch_rows)
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if pass_condition else 1)


if __name__ == "__main__":
    main()
