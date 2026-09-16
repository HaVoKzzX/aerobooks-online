"""Full-data backup and restore (database, invoice PDFs, QR codes, settings).

Portable zips use the same layout as desktop AeroBooks, so a backup from the
original program restores here, and a backup from here restores in the original.
Files stored on this server are encrypted at rest.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from aerobooks import paths
from aerobooks.crypto import is_encrypted
from aerobooks.store import enc_path, export_sqlite, secure_read, secure_write

MANIFEST_NAME = "manifest.json"
ZIP_ROOT = "AeroBooks-backup"


def _checkpoint() -> None:
    """No-op for encrypted in-memory DBs; kept so callers stay the same."""
    return


def _write_manifest(folder: Path) -> None:
    payload = {
        "app": "AeroBooks",
        "edition": paths.APP_NAME,
        "version": paths.APP_VERSION,
        "created": datetime.now().isoformat(timespec="seconds"),
        "includes": ["aerobooks.db", "invoices/", "qr/"],
        "compatible_with": ["AeroBooks", "AeroBooks Online"],
    }
    (folder / MANIFEST_NAME).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _copy_folder_decrypted(src: Path, dest: Path) -> None:
    if not src.exists():
        return
    dest.mkdir(parents=True, exist_ok=True)
    for item in src.rglob("*"):
        if not item.is_file():
            continue
        rel = item.relative_to(src)
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(secure_read(item))


def _has_db() -> bool:
    db_file = paths.db_path()
    return db_file.exists() or enc_path(db_file).exists()


def create_backup_zip(dest: Path | None = None) -> Path:
    """Zip everything the instructor owns into a desktop-compatible file."""
    from aerobooks import auth, db

    if not auth.can_backup():
        raise PermissionError("Backups are available to the account owner or school manager.")

    db.init_db()
    paths.ensure_data_dirs()

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    filename = f"AeroBooks-backup-{stamp}.zip"
    if dest is None:
        dest = paths.documents_backup_dir() / filename
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()

    staging = Path(tempfile.mkdtemp(prefix="aerobooks-bak-"))
    try:
        root = staging / ZIP_ROOT
        root.mkdir()
        blob = export_sqlite(paths.db_path())
        if blob:
            (root / "aerobooks.db").write_bytes(blob)
        data = paths.data_dir()
        for folder_name in ("invoices", "qr"):
            _copy_folder_decrypted(data / folder_name, root / folder_name)
        _write_manifest(root)
        plain_zip = staging / filename
        with zipfile.ZipFile(plain_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for item in root.rglob("*"):
                if item.is_file():
                    zf.write(item, item.relative_to(staging).as_posix())
        zip_bytes = plain_zip.read_bytes()
        in_data_tree = False
        try:
            in_data_tree = dest.resolve().is_relative_to(paths.base_data_dir().resolve())
        except Exception:
            in_data_tree = str(dest.resolve()).startswith(str(paths.base_data_dir().resolve()))
        if in_data_tree:
            secure_write(dest, zip_bytes)
        else:
            dest.write_bytes(zip_bytes)
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    local_copy = paths.local_backup_dir() / dest.name
    local_copy.parent.mkdir(parents=True, exist_ok=True)
    if local_copy.resolve() != dest.resolve():
        secure_write(local_copy, zip_bytes)
    portable = paths.original_desktop_backup_dir() / dest.name
    try:
        if portable.resolve() != dest.resolve():
            portable.parent.mkdir(parents=True, exist_ok=True)
            portable.write_bytes(zip_bytes)
    except OSError:
        pass
    return dest


def _looks_like_backup(folder: Path) -> bool:
    if (folder / "aerobooks.db").exists():
        return True
    nested = folder / ZIP_ROOT
    return (nested / "aerobooks.db").exists()


def _backup_root(extracted: Path) -> Path:
    if (extracted / "aerobooks.db").exists():
        return extracted
    nested = extracted / ZIP_ROOT
    if (nested / "aerobooks.db").exists():
        return nested
    for child in extracted.iterdir():
        if child.is_dir() and (child / "aerobooks.db").exists():
            return child
    raise ValueError(
        "This file is not an AeroBooks backup (no database found). "
        "Use a zip created by AeroBooks or AeroBooks Online (AeroBooks-backup-*.zip)."
    )


def _as_zip_path(zip_path: Path) -> tuple[Path, Path | None]:
    """Return a plaintext zip path, and an optional temp file to delete."""
    raw = zip_path.read_bytes()
    if is_encrypted(raw):
        tmp = Path(tempfile.mkdtemp(prefix="aerobooks-unz-")) / zip_path.name
        tmp.write_bytes(secure_read(zip_path))
        return tmp, tmp.parent
    return zip_path, None


def restore_from_zip(zip_path: Path, *, keep_safety_copy: bool = True) -> Path | None:
    """Replace current data with a backup zip from AeroBooks or AeroBooks Online."""
    from aerobooks import auth, db
    from aerobooks.store import encrypt_tree

    if not auth.can_backup():
        raise PermissionError("Restore is available to the account owner or school manager.")
    zip_path = Path(zip_path)
    if not zip_path.exists():
        raise FileNotFoundError(f"Backup not found: {zip_path}")

    safety: Path | None = None
    if keep_safety_copy and _has_db():
        safety_name = f"AeroBooks-before-restore-{datetime.now().strftime('%Y-%m-%d_%H%M')}.zip"
        safety = paths.documents_backup_dir() / safety_name
        try:
            create_backup_zip(safety)
        except Exception:
            safety = None

    staging = Path(tempfile.mkdtemp(prefix="aerobooks-rst-"))
    unpacked = None
    try:
        readable, unpacked = _as_zip_path(zip_path)
        if not zipfile.is_zipfile(readable):
            raise ValueError("That file is not a zip backup.")
        with zipfile.ZipFile(readable, "r") as zf:
            zf.extractall(staging)
        root = _backup_root(staging)
        if not _looks_like_backup(root):
            raise ValueError("This zip does not look like an AeroBooks backup.")

        dest = paths.data_dir()
        dest.mkdir(parents=True, exist_ok=True)

        target_db = dest / "aerobooks.db"
        for leftover in (
            target_db,
            dest / "aerobooks.db-wal",
            dest / "aerobooks.db-shm",
            enc_path(target_db),
        ):
            if leftover.exists():
                leftover.unlink()

        db_bytes = (root / "aerobooks.db").read_bytes()
        if is_encrypted(db_bytes):
            from aerobooks.crypto import decrypt_bytes

            db_bytes = decrypt_bytes(db_bytes)
        target_db.write_bytes(db_bytes)
        wal_src = root / "aerobooks.db-wal"
        if wal_src.exists() and wal_src.stat().st_size:
            shutil.copy2(wal_src, dest / "aerobooks.db-wal")
        shm = dest / "aerobooks.db-shm"
        if shm.exists():
            shm.unlink()

        for folder_name in ("invoices", "qr"):
            src = root / folder_name
            target = dest / folder_name
            if target.exists():
                shutil.rmtree(target)
            if src.exists():
                shutil.copytree(src, target)
            else:
                target.mkdir(parents=True, exist_ok=True)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        if unpacked:
            shutil.rmtree(unpacked, ignore_errors=True)

    db.init_db()
    user = auth.current_user()
    if user and user.get("id"):
        db.adopt_unassigned_records(int(user["id"]))
    encrypt_tree(paths.invoice_dir())
    encrypt_tree(paths.qr_dir())
    _fix_restored_paths()
    return safety


def _fix_restored_paths() -> None:
    from aerobooks import db

    custom = db.get_setting("custom_qr_path")
    if not custom:
        return
    name = Path(custom).name
    candidate = paths.qr_dir() / name
    if candidate.exists():
        db.set_setting("custom_qr_path", str(candidate))


def list_backups() -> list[dict]:
    found: dict[str, Path] = {}
    folders = [
        paths.documents_backup_dir(),
        paths.local_backup_dir(),
        paths.original_desktop_backup_dir(),
    ]
    for folder in folders:
        if not folder.exists():
            continue
        for pattern in ("AeroBooks-backup-*.zip", "AeroBooks-before-restore-*.zip"):
            for item in folder.glob(pattern):
                found[str(item.resolve())] = item
    rows = []
    origin = paths.original_desktop_backup_dir()
    for path in sorted(found.values(), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            from_desktop = path.resolve().is_relative_to(origin.resolve())
        except Exception:
            from_desktop = path.parent == origin
        source = "Original AeroBooks" if from_desktop else "This workspace"
        rows.append(
            {
                "name": path.name,
                "path": str(path),
                "size": path.stat().st_size,
                "modified": datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                "folder": str(path.parent),
                "source": source,
            }
        )
    return rows


def open_folder(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    os_start(folder)


def os_start(target: Path) -> None:
    import os

    if os.name == "nt":
        os.startfile(str(target))  # type: ignore[attr-defined]
    else:
        import subprocess

        subprocess.Popen(["xdg-open", str(target)])
