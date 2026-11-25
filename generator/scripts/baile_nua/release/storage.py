"""Is there a genuinely external drive, and how much room is really on it?

This exists because of I-036. `/Volumes/Vault` reports itself as

    Device Location:  External
    Removable Media:  Removable
    Disk Size:        536.7 GB
    Container Free:   536.5 GB

and it is a 536 GB encrypted **sparse bundle** whose backing file is
`/Users/brianoregan/Vault.sparsebundle` on the internal disk. Every byte
written into it consumes internal space. `df` happily reports 536 GB free on
it and 74 GiB free on `/`, and only one of those numbers is real.

So "External" and "Removable" from `diskutil` cannot be trusted: that is the
disk-image driver describing itself. The discriminator is the **protocol** and
the **physical store**. A disk image's protocol is literally `Disk Image`, and
`hdiutil info` names the backing file - which is the thing that tells you
where the bytes will actually land.

The same shape of trap as I-017, where a Met Éireann file downloaded cleanly,
parsed cleanly, contained entirely plausible Irish weather, and was the wrong
station. A thing that answers confidently is not a thing that answers
correctly.
"""

from __future__ import annotations

import dataclasses
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

__all__ = ["VolumeFacts", "inspect_volume", "find_external_drive", "storage_report"]


@dataclasses.dataclass
class VolumeFacts:
    """What a mount point actually is, as distinct from what it claims."""

    mount_point: str
    exists: bool
    protocol: str | None = None
    device_node: str | None = None
    claims_external: bool = False
    claims_removable: bool = False
    is_disk_image: bool = False
    backing_file: str | None = None
    backing_on_internal: bool | None = None
    free_bytes: int = 0
    total_bytes: int = 0
    #: The verdict, and the only field a caller should branch on.
    usable_as_external: bool = False
    reason: str = ""

    @property
    def free_gb(self) -> float:
        return self.free_bytes / 1024**3

    def as_row(self) -> dict[str, Any]:
        d = dataclasses.asdict(self)
        d["free_gb"] = round(self.free_gb, 2)
        d["total_gb"] = round(self.total_bytes / 1024**3, 2)
        return d


def _run(cmd: list[str], timeout: int = 20) -> str:
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        ).stdout
    except (OSError, subprocess.SubprocessError):       # pragma: no cover
        return ""


def _disk_image_backing_files() -> dict[str, str]:
    """Device node -> backing file, for every mounted disk image."""
    out: dict[str, str] = {}
    text = _run(["hdiutil", "info"])
    image_path: str | None = None
    for line in text.splitlines():
        m = re.match(r"\s*image-path\s*:\s*(.+?)\s*$", line)
        if m:
            image_path = m.group(1)
            continue
        m = re.match(r"\s*(/dev/disk\d+\S*)\s", line)
        if m and image_path:
            out[m.group(1)] = image_path
    return out


def _mount_point_of(path: str | Path) -> Path:
    """The mount point holding ``path``, by walking up until the device changes."""
    p = Path(path).resolve()
    while not p.is_mount() and p != p.parent:
        p = p.parent
    return p


def _backing_is_internal(backing_file: str, _depth: int = 0) -> bool | None:
    """Is a disk image's backing file ultimately on a non-external volume?

    Recursive, because a disk image can sit inside another disk image. Bounded,
    because a cycle would otherwise hang the check, and a storage probe that
    hangs is worse than one that answers "unknown".
    """
    if _depth > 4:                                       # pragma: no cover
        return None
    try:
        mount = _mount_point_of(backing_file)
    except OSError:                                      # pragma: no cover
        return None
    if str(mount) == "/":
        return True
    holder = inspect_volume(mount)
    if holder.is_disk_image and holder.backing_file:
        return _backing_is_internal(holder.backing_file, _depth + 1)
    return not holder.usable_as_external


def inspect_volume(mount_point: str | Path) -> VolumeFacts:
    """Establish what a mount point is, not what it says it is."""
    mp = str(mount_point)
    facts = VolumeFacts(mount_point=mp, exists=Path(mp).exists())
    if not facts.exists:
        facts.reason = "the path does not exist"
        return facts

    try:
        usage = shutil.disk_usage(mp)
        facts.free_bytes, facts.total_bytes = usage.free, usage.total
    except OSError as exc:                              # pragma: no cover
        facts.reason = f"cannot stat: {exc}"
        return facts

    info = _run(["diskutil", "info", mp])
    for key, attr in (
        ("Protocol", "protocol"),
        ("Device Node", "device_node"),
    ):
        m = re.search(rf"^\s*{key}:\s*(.+?)\s*$", info, re.M)
        if m:
            setattr(facts, attr, m.group(1))
    facts.claims_external = bool(
        re.search(r"^\s*Device Location:\s*External", info, re.M)
    )
    facts.claims_removable = bool(
        re.search(r"^\s*Removable Media:\s*Removable", info, re.M)
    )
    facts.is_disk_image = (facts.protocol or "").strip().lower() == "disk image"

    if facts.is_disk_image:
        backing = _disk_image_backing_files()
        # The volume's own node, or its container's, may be the one listed.
        node = facts.device_node or ""
        candidates = [node, re.sub(r"s\d+$", "", node)]
        for cand in candidates:
            for dev, path in backing.items():
                if dev.startswith(cand) or cand.startswith(dev):
                    facts.backing_file = path
                    break
            if facts.backing_file:
                break
        if facts.backing_file:
            # Where do the bytes actually land? Resolve the backing file to the
            # volume that HOLDS it and ask whether that volume is external.
            #
            # Comparing st_dev against "/" is the obvious check and it is
            # wrong: on APFS the boot volume and the Data volume are separate
            # volumes with different device ids while sharing one physical
            # disk, so a backing file in /Users compares as "not on /" and the
            # check silently returns the wrong answer. It returned None here,
            # which at least did not lie.
            facts.backing_on_internal = _backing_is_internal(facts.backing_file)
        facts.usable_as_external = False
        facts.reason = (
            f"a disk image, not a drive: protocol {facts.protocol!r}, backing "
            f"file {facts.backing_file or 'unknown'}"
            + (
                " which is on the internal disk, so its free space is the "
                "internal disk's free space counted twice"
                if facts.backing_on_internal else ""
            )
            + (
                f". It reports Device Location External and Removable Media "
                f"Removable; that is the disk-image driver describing itself "
                f"(I-036)."
                if (facts.claims_external or facts.claims_removable) else "."
            )
        )
        return facts

    external_protocols = {
        "usb", "thunderbolt", "sata", "pci-express", "fibre channel",
        "sd card", "firewire", "nvme express",
    }
    proto = (facts.protocol or "").strip().lower()
    if facts.claims_external and proto in external_protocols:
        facts.usable_as_external = True
        facts.reason = f"physically external over {facts.protocol}"
    else:
        facts.usable_as_external = False
        facts.reason = (
            f"not established as externally attached: protocol "
            f"{facts.protocol!r}, Device Location External="
            f"{facts.claims_external}"
        )
    return facts


def find_external_drive(
    *, min_free_bytes: int = 0, volumes_dir: str = "/Volumes",
) -> tuple[VolumeFacts | None, list[dict[str, Any]]]:
    """The first genuinely external volume with enough room, and every candidate.

    Returns ``(chosen, all_candidates)``. ``chosen`` is ``None`` when nothing
    qualifies, which is the case the storage fallback exists for. Every
    candidate is returned with its verdict and reason so a report can say what
    was rejected and why, rather than only that nothing was found.
    """
    root = Path(volumes_dir)
    candidates: list[dict[str, Any]] = []
    chosen: VolumeFacts | None = None
    if root.exists():
        for entry in sorted(root.iterdir()):
            if entry.is_symlink():          # "Macintosh HD -> /"
                continue
            facts = inspect_volume(entry)
            candidates.append(facts.as_row())
            if (
                chosen is None
                and facts.usable_as_external
                and facts.free_bytes >= min_free_bytes
            ):
                chosen = facts
    return chosen, candidates


def storage_report(*, required_bytes: int = 0) -> dict[str, Any]:
    """Everything the week 3 storage decision needs, measured now."""
    chosen, candidates = find_external_drive(min_free_bytes=required_bytes)
    internal = shutil.disk_usage("/")
    return {
        "design_ref": "U24; U28 and its storage-fallback amendment; I-036",
        "required_bytes": int(required_bytes),
        "required_gb": round(required_bytes / 1024**3, 2),
        "internal_free_gb": round(internal.free / 1024**3, 2),
        "external_drive_found": chosen is not None,
        "external_drive": (chosen.as_row() if chosen else None),
        "candidates_examined": candidates,
        "note": (
            "A volume qualifies only on its PROTOCOL and physical store, never "
            "on its own claim to be External or Removable. I-036's candidate "
            "made both claims and was a sparse bundle on the internal disk."
        ),
    }
