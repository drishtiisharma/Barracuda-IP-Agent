"""
Builds ONE small, self-contained executable.

    python build_exe.py                  normal build
    python build_exe.py --upx-dir C:/upx   (optional) also compress with UPX if you have it -> even smaller

Run it on the OS you are targeting: build on Windows to get a Windows .exe.
(PyInstaller cannot cross-compile; a Mac/Linux build gives a Mac/Linux program.)

The exe contains no browser: it drives the Microsoft Edge / Google Chrome already installed on the PC
(Windows 10 and 11 always have Edge).
"""
import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(cmd, **kw):
    print(">", " ".join(str(c) for c in cmd))
    subprocess.check_call([str(c) for c in cmd], **kw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--upx-dir", help="folder that contains upx(.exe); makes the exe smaller still")
    args = ap.parse_args()

    os.chdir(HERE)
    if not importlib.util.find_spec("PyInstaller"):
        run([sys.executable, "-m", "pip", "install", "-r", "requirements-build.txt"])

    for folder in ("build", "dist"):
        shutil.rmtree(HERE / folder, ignore_errors=True)

    env = dict(os.environ)
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean"]
    if args.upx_dir:
        env["BARRACUDA_UPX"] = "1"
        cmd += ["--upx-dir", args.upx_dir]
    cmd.append("BarracudaIPAgent.spec")
    run(cmd, env=env)

    exe = HERE / "dist" / ("BarracudaIPAgent.exe" if sys.platform.startswith("win") else "BarracudaIPAgent")
    if not exe.exists():
        sys.exit("Build finished but the executable was not found in dist/.")
    mb = exe.stat().st_size / 1e6
    print(f"\nDone. Give this single file to anyone:\n  {exe}  ({mb:.1f} MB)")
    if mb >= 10 and not args.upx_dir:
        print("Tip: install UPX (https://upx.github.io) and run  python build_exe.py --upx-dir <folder with upx.exe>")
    shutil.rmtree(HERE / "build", ignore_errors=True)       # the intermediate build folder is not needed afterwards


if __name__ == "__main__":
    main()
