#!/usr/bin/env python3
"""Build Iris's Counter from the MIT-licensed Frame Window Lab source."""
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / ".upstream-frame-window-lab"

def replace(path, before, after):
    contents = path.read_text(encoding="utf-8")
    if before not in contents:
        raise RuntimeError(f"Expected source anchor missing in {path}: {before!r}")
    path.write_text(contents.replace(before, after), encoding="utf-8")

def main():
    if not UPSTREAM.exists():
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", "main",
             "https://github.com/ousertri842/framecounterv2.git", str(UPSTREAM)],
            check=True,
        )
    for name in ("src", "resources", "tests", "CMakeLists.txt", "mod.json",
                 "LICENSE", "logo.png", "about.md"):
        source, dest = UPSTREAM / name, ROOT / name
        if not source.exists():
            raise RuntimeError(f"Missing upstream file: {source}")
        if dest.is_dir():
            shutil.rmtree(dest)
        elif dest.exists():
            dest.unlink()
        if source.is_dir():
            shutil.copytree(source, dest)
        else:
            shutil.copy2(source, dest)
    shutil.copy2(UPSTREAM / "README.md", ROOT / "UPSTREAM_README.md")
    # Pin the audited open-source mirror of the original MIT-licensed project.
    expected = "db0b2b781d201861c22955fd3fa03ff685db5050"
    actual = subprocess.run(
        ["git", "-C", str(UPSTREAM), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True
    ).stdout.strip()
    if actual != expected:
        raise RuntimeError(f"Upstream mirror changed unexpectedly: {actual}; expected {expected}")

    manifest_file = ROOT / "mod.json"
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    manifest.update({
        "id": "iris.counter",
        "name": "Iris's Counter",
        "developer": "Iris",
        "description": "Offline Geometry Dash frame-window recorder, scanner and replay counter, based on Frame Window Lab by Razor (MIT).",
    })
    manifest_file.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    replace(ROOT / "src" / "Overlay.cpp", '"FRAME WINDOWS"', '"Iris\'s Counter"')
    replace(ROOT / "src" / "Overlay.cpp", "float width = 112.f;", "float width = 144.f;")
    replace(ROOT / "src" / "Menu.cpp",
            'this->setTitle("Frame Window Lab",',
            'this->setTitle("Iris\'s Counter",')
    replace(ROOT / "CMakeLists.txt", "project(FrameWindowLab VERSION",
            "project(IrisCounter VERSION")
    # Add practice checkpoint recorder before cosmetic renaming of upstream strings.
    subprocess.run(["python", str(ROOT / "scripts" / "patch_practice.py")], check=True)

    for path in list((ROOT / "src").rglob("*.cpp")) + list((ROOT / "src").rglob("*.hpp")):
        contents = path.read_text(encoding="utf-8")
        if "Frame Window Lab" in contents:
            path.write_text(contents.replace("Frame Window Lab", "Iris's Counter"), encoding="utf-8")
    (ROOT / "about.md").write_text(
        "# Iris's Counter\n\nOffline frame-window recorder, scanner and replay with click rings and counter rows.\n\n"
        "Pause a classic level and open the counter button. You can record in practice mode and keep the successful inputs across checkpoint respawns; finish, then Scan and Play. No license key required.\n\n"
        "Independent adaptation of Frame Window Lab by Razor, MIT license. Not affiliated with FB Mods.\n",
        encoding="utf-8",
    )
    print("Iris's Counter source is ready.")

if __name__ == "__main__":
    main()
