"""Dew's egglog wheels: PyPI's own wheels of the release this branch patches, each with the branch's Python package
in place of the release's and this branch's version (pyproject.toml), the Rust extension the release built kept byte
for byte. The patch is to the Python package alone (python/egglog), so no Rust is rebuilt: what the release tested
natively is what runs.

    python dew/repack.py RELEASE OUT [PLATFORM...]    e.g. 14.0.0 dist manylinux_2_17_x86_64 manylinux_2_17_aarch64

Each wheel's download is checked against PyPI's digest, its extension and every file the branch does not change are
checked unchanged, and its RECORD is written again (PEP 376/427).
"""

import base64
import csv
import hashlib
import io
import json
import sys
import tomllib
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


def record_hash(data: bytes) -> str:
    return "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()


def repacked(name: str, data: bytes, release: str, version: str) -> tuple[str, bytes]:
    """Wheel `name` (`data`) of `release` as `version`: the branch's python/egglog files in place of its own."""
    source = zipfile.ZipFile(io.BytesIO(data))
    old_info, new_info = f"egglog-{release}.dist-info", f"egglog-{version}.dist-info"
    files: dict[str, bytes] = {}
    for item in source.infolist():
        if item.filename == f"{old_info}/RECORD":
            continue
        body = source.read(item)
        path = item.filename
        if path.startswith("egglog/") and path.endswith(".py"):
            branch = HERE / "python" / path
            if not branch.is_file():
                raise SystemExit(f"{name}: {path} is not the branch's")
            body = branch.read_bytes()
        if path.startswith(f"{old_info}/"):
            path = new_info + path[len(old_info):]
            if path == f"{new_info}/METADATA":
                text = body.decode()
                if f"\nVersion: {release}\n" not in text:
                    raise SystemExit(f"{name}: its METADATA states no version {release}")
                body = text.replace(f"\nVersion: {release}\n", f"\nVersion: {version}\n", 1).encode()
        files[path] = body
    # The branch's package holds no file the release's does not.
    shipped = {path for path in files if path.startswith("egglog/") and path.endswith(".py")}
    branch = {f"egglog/{path.relative_to(HERE / 'python' / 'egglog').as_posix()}"
              for path in (HERE / "python" / "egglog").rglob("*.py")}
    if branch - shipped:
        raise SystemExit(f"{name}: the branch adds {sorted(branch - shipped)}, which a repack cannot carry")
    out = io.BytesIO()
    record = io.StringIO()
    writer = csv.writer(record, lineterminator="\n")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as wheel:
        for path, body in files.items():
            wheel.writestr(path, body)
            writer.writerow([path, record_hash(body), len(body)])
        writer.writerow([f"{new_info}/RECORD", "", ""])
        wheel.writestr(f"{new_info}/RECORD", record.getvalue())
    return name.replace(f"egglog-{release}-", f"egglog-{version}-", 1), out.getvalue()


def main() -> int:
    release, out, *platforms = sys.argv[1:]
    version = tomllib.loads((HERE / "pyproject.toml").read_text())["project"]["version"]
    found = json.load(urllib.request.urlopen(f"https://pypi.org/pypi/egglog/{release}/json"))
    Path(out).mkdir(parents=True, exist_ok=True)
    for file in found["urls"]:
        name = file["filename"]
        if file["packagetype"] != "bdist_wheel" or (platforms and not any(p in name for p in platforms)):
            continue
        data = urllib.request.urlopen(file["url"]).read()
        if hashlib.sha256(data).hexdigest() != file["digests"]["sha256"]:
            raise SystemExit(f"{name}: its download differs from PyPI's digest")
        made, body = repacked(name, data, release, version)
        (Path(out) / made).write_bytes(body)
        print(made)
    return 0


if __name__ == "__main__":
    sys.exit(main())
