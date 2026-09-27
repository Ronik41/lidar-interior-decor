#!/usr/bin/env python3
"""Verify and archive a RoomScan ZIP or folder received from an iPhone."""

import argparse
import contextlib
import hashlib
import json
import math
import os
import plistlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path, PurePosixPath

REQUIRED = {"Room.json", "Room.usdz"}
REFERENCE = {"Reference.jpg", "Reference.json"}
MAX_PACKAGE_BYTES = 1024 * 1024 * 1024  # A single-room prototype, at most 1 GiB.


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path.name}")
    return value


def validate(source: Path) -> dict:
    manifest_path = source / "manifest.json"
    if not source.is_dir() or not manifest_path.is_file() or manifest_path.is_symlink():
        raise ValueError(f"Not a RoomScan folder: {source}")
    manifest = read_object(manifest_path)
    if type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1:
        raise ValueError("Unsupported scan package version")
    scan_id = manifest.get("scan_id")
    try:
        if not isinstance(scan_id, str) or str(uuid.UUID(scan_id)) != scan_id:
            raise ValueError()
    except ValueError:
        raise ValueError("Invalid scan ID") from None
    hashes = manifest.get("sha256")
    if not isinstance(hashes, dict) or not REQUIRED.issubset(hashes):
        raise ValueError("Room JSON or USDZ is missing from the manifest")
    if set(hashes) - (REQUIRED | REFERENCE):
        raise ValueError("Unexpected file name in manifest")
    rgb = manifest.get("rgb_reference_available")
    if type(rgb) is not bool or set(hashes) != REQUIRED | (REFERENCE if rgb else set()):
        raise ValueError("RGB reference files do not match the manifest")
    for name, expected in hashes.items():
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError(f"Invalid SHA-256 checksum: {name}")
        path = source / name
        if path.is_symlink() or not path.is_file() or file_hash(path) != expected:
            raise ValueError(f"Missing or damaged file: {name}")
    room = read_object(source / "Room.json")
    if not isinstance(room.get("walls"), list) or not room["walls"]:
        raise ValueError("Room JSON has no captured walls")
    try:
        with zipfile.ZipFile(source / "Room.usdz") as model:
            members = model.infolist()
            if (not members or PurePosixPath(members[0].filename).suffix.lower()
                    not in {".usd", ".usda", ".usdc"}):
                raise ValueError("USDZ has no root USD model")
            if sum(item.file_size for item in members) > MAX_PACKAGE_BYTES:
                raise ValueError("USDZ exceeds the 1 GiB prototype limit")
            if any(item.compress_type != zipfile.ZIP_STORED for item in members) or model.testzip():
                raise ValueError("Damaged or compressed USDZ container")
    except zipfile.BadZipFile as error:
        raise ValueError("Room.usdz is not a readable USDZ archive") from error
    if rgb:
        metadata = read_object(source / "Reference.json")
        for key, count in (("camera_to_world_column_major", 16), ("intrinsics_column_major", 9)):
            values = metadata.get(key)
            if (not isinstance(values, list) or len(values) != count
                    or not all(type(v) in (int, float) and math.isfinite(v) for v in values)):
                raise ValueError(f"Invalid camera metadata: {key}")
        for key in ("image_width", "image_height"):
            if type(metadata.get(key)) is not int or metadata[key] <= 0:
                raise ValueError(f"Invalid camera metadata: {key}")
        timestamp = metadata.get("timestamp_seconds")
        if type(timestamp) not in (int, float) or not math.isfinite(timestamp):
            raise ValueError("Invalid camera metadata: timestamp_seconds")
        with (source / "Reference.jpg").open("rb") as image:
            if image.read(3) != b"\xff\xd8\xff":
                raise ValueError("Reference.jpg is not a JPEG")
    return manifest


@contextlib.contextmanager
def package_folder(source: Path):
    if source.is_dir():
        yield source
        return
    if not source.is_file():
        raise ValueError(f"Scan package does not exist: {source}")
    with tempfile.TemporaryDirectory(prefix="roomscan-unzip-") as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(source) as archive:
            members = archive.infolist()
            if len(members) > 100 or sum(m.file_size for m in members) > MAX_PACKAGE_BYTES:
                raise ValueError("ZIP exceeds the single-room prototype limit")
            seen = set()
            for member in members:
                name = member.filename
                path = PurePosixPath(name)
                if (path.is_absolute() or ".." in path.parts or "\\" in name
                        or stat.S_ISLNK(member.external_attr >> 16) or name in seen):
                    raise ValueError(f"Unsafe or duplicate ZIP entry: {name}")
                seen.add(name)
                if "__MACOSX" in path.parts or path.name == ".DS_Store":
                    continue
                archive.extract(member, root)
        manifests = list(root.rglob("manifest.json"))
        if len(manifests) != 1:
            raise ValueError("ZIP must contain exactly one scan manifest")
        yield manifests[0].parent


def import_scan(source: Path, destination_root: Path) -> Path:
    source = source.expanduser().resolve()
    destination_root = destination_root.expanduser().resolve()
    with package_folder(source) as folder:
        manifest = validate(folder)
        destination_root.mkdir(parents=True, exist_ok=True)
        destination = destination_root / manifest["scan_id"]
        if destination.exists():
            if validate(destination) == manifest:
                print(f"Already imported and verified: {destination}")
                return destination
            raise ValueError(f"Scan ID already exists with different contents: {destination}")
        with tempfile.TemporaryDirectory(prefix=".incoming-", dir=destination_root) as temporary:
            staging = Path(temporary) / "scan"
            staging.mkdir()
            for name in ["manifest.json", *manifest["sha256"]]:
                shutil.copy2(folder / name, staging / name)
            validate(staging)
            os.replace(staging, destination)
    print(f"Imported and verified {len(manifest['sha256'])} file checksums: {destination}")
    print(f"Room model: {destination / 'Room.usdz'}")
    print(f"Room data:  {destination / 'Room.json'}")
    print(f"RGB image:  {destination / 'Reference.jpg' if manifest['rgb_reference_available'] else 'unavailable for this scan'}")
    return destination


def open_scan(destination: Path):
    if sys.platform != "darwin":
        raise ValueError("--open uses the local macOS model viewer, Finder, and TextEdit")
    viewer_source = Path(__file__).with_name("view_room.swift")
    app = Path(__file__).parent / ".build" / "RoomScanViewer.app"
    executable = app / "Contents" / "MacOS" / "RoomScanViewer"
    if not executable.exists() or executable.stat().st_mtime < viewer_source.stat().st_mtime:
        executable.parent.mkdir(parents=True, exist_ok=True)
        print("Building local model viewer…", flush=True)
        subprocess.run(["xcrun", "swiftc", str(viewer_source), "-o", str(executable)], check=True)
        (app / "Contents" / "Info.plist").write_bytes(plistlib.dumps({
            "CFBundleExecutable": "RoomScanViewer", "CFBundleIdentifier": "local.roomscan.viewer",
            "CFBundleName": "Room Scan Viewer", "CFBundlePackageType": "APPL",
        }))
    # Decode the model before launching so a malformed USD reports a CLI error.
    subprocess.run([str(executable), "--check", str(destination / "Room.usdz")], check=True)
    subprocess.run(["open", str(destination)], check=True)
    subprocess.run(["open", "-a", "TextEdit", str(destination / "Room.json")], check=True)
    if (destination / "Reference.jpg").exists():
        subprocess.run(["open", str(destination / "Reference.jpg")], check=True)
    subprocess.run(["open", "-n", str(app), "--args", str(destination / "Room.usdz")], check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="AirDropped RoomScan ZIP or extracted folder")
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "scans")
    parser.add_argument("--open", action="store_true", help="Open imported model, JSON, and optional RGB on this Mac")
    args = parser.parse_args()
    try:
        destination = import_scan(args.source, args.out)
        if args.open:
            open_scan(destination)
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError, subprocess.SubprocessError) as error:
        print(f"Import/open failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
