# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['/home/slayer/PycharmProjects/OpenBoard/main.py'],
    pathex=[],
    binaries=[],
    datas=[('/home/slayer/PycharmProjects/OpenBoard/assets/build', 'assets/build'), ('/home/slayer/PycharmProjects/OpenBoard/THIRD_PARTY_LICENSES.md', '.'), ('/home/slayer/PycharmProjects/OpenBoard/bin/stockfish/linux', 'bin/stockfish/linux')],
    hiddenimports=['chess', 'chess.engine', 'chess.polyglot', 'platformdirs'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='OpenBoard',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['/home/slayer/PycharmProjects/OpenBoard/assets/build/icons/icon.png'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='OpenBoard',
)
