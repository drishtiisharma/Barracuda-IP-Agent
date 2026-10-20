# -*- mode: python ; coding: utf-8 -*-
# PyInstaller recipe tuned for the smallest possible single-file executable.
#   - no Playwright / Chromium / Node.js (the PC's own Edge/Chrome is used)
#   - no SSL / OpenSSL (everything talks to localhost), no email/http/xml/asyncio/unittest/...
#   - Tcl/Tk translation files and time-zone data are dropped
import os

UPX = os.environ.get("BARRACUDA_UPX") == "1"

EXCLUDES = [
    "ssl", "_ssl", "hashlib", "_hashlib", "hmac", "secrets",
    "unittest", "doctest", "pydoc", "pydoc_data", "test", "idlelib", "lib2to3", "turtle", "turtledemo",
    "email", "http", "xml", "xmlrpc", "html", "ftplib", "smtplib", "imaplib", "poplib", "telnetlib",
    "asyncio", "concurrent", "multiprocessing", "curses", "_curses", "readline",
    "bz2", "_bz2", "lzma", "_lzma", "distutils", "setuptools", "pkg_resources",
    "decimal", "_decimal", "_pydecimal", "fractions", "statistics",
    "numpy", "PIL", "pandas", "matplotlib",
    # Chinese / Japanese / Korean text codecs (not needed: everything we write is UTF-8)
    "_multibytecodec", "_codecs_cn", "_codecs_hk", "_codecs_iso2022", "_codecs_jp", "_codecs_kr", "_codecs_tw",
    "encodings.big5", "encodings.big5hkscs", "encodings.cp932", "encodings.cp949", "encodings.cp950",
    "encodings.euc_jp", "encodings.euc_jis_2004", "encodings.euc_jisx0213", "encodings.euc_kr",
    "encodings.gb2312", "encodings.gbk", "encodings.gb18030", "encodings.hz", "encodings.johab",
    "encodings.iso2022_jp", "encodings.iso2022_jp_1", "encodings.iso2022_jp_2", "encodings.iso2022_jp_2004",
    "encodings.iso2022_jp_3", "encodings.iso2022_jp_ext", "encodings.iso2022_kr",
    "encodings.shift_jis", "encodings.shift_jis_2004", "encodings.shift_jisx0213",
]

a = Analysis(
    ["main.py"],
    pathex=["."],
    datas=[("assets/logo.ico", "assets"), ("assets/logo_64.png", "assets")],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=2,
)


# Tcl text-encoding tables for CJK languages (large, never used by this app)
_CJK_TCL = ("cp932", "cp936", "cp949", "cp950", "big5", "euc-", "gb", "jis", "ksc5601", "shiftjis",
            "iso2022", "macjapan", "macchinese", "maccroatian_", "cns11643")


def _wanted(entry):
    dest = entry[0].replace("\\", "/").lower()
    if any(part in dest for part in ("tzdata", "/msgs/", "tcl8/")):
        return False
    if "/encoding/" in dest and dest.rsplit("/", 1)[-1].startswith(_CJK_TCL):
        return False
    return True


a.datas = [d for d in a.datas if _wanted(d)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="BarracudaIPAgent",
    icon="assets/logo.ico",
    console=False,
    debug=False,
    strip=False,
    upx=UPX,
    runtime_tmpdir=None,
)
