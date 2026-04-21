# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['app\\launcher\\main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('app/frontend/assets', 'app/frontend/assets'),
        ('config', 'config'),
        ('tools', 'tools'), 
    ],
    hiddenimports=[
        'pandas',
        'pandas._libs.tslibs.base',
        'pandas._libs.tslibs.np_datetime',
        'numpy',
        'app.frontend.pages.build_page',
        'app.frontend.pages.configuration_page',
        'app.frontend.pages.home_page',
        'app.frontend.pages.metadata_page',
        'app.frontend.pages.parameters_page',
        'app.frontend.pages.splash_screen',
        'app.frontend.components.sidebar_button',
        'app.frontend.components.features_editor',
        'app.frontend.components.instances_editor',
        'app.frontend.components.instance_space_editor',
        'app.frontend.components.metadata_orchestrator_config_editor',
        'app.frontend.components.solvers_editor',
        'app.backend.services.config_service',
        'tools.installation.check_environment',
    ],
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
    name='SDISG',
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
    icon='app\\frontend\\assets\\icons\\sdisg_icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SDISG',
)