# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for JARVIS.app front-end.
Freezes ONLY app/main.py + GUI/capture deps.
The Flask backend (ui/server.py) is NOT frozen — it runs as a venv subprocess.
"""
from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None

# Collect all files for packages that have native binaries or data
sd_datas, sd_binaries, sd_hiddenimports = collect_all('sounddevice')
cv2_datas, cv2_binaries, cv2_hiddenimports = collect_all('cv2')
wv_datas, wv_binaries, wv_hiddenimports = collect_all('webview')

a = Analysis(
    ['app/main.py'],
    pathex=['.'],
    binaries=sd_binaries + cv2_binaries + wv_binaries,
    datas=(
        sd_datas + cv2_datas + wv_datas +
        [('app/icon.icns', '.')]
    ),
    hiddenimports=(
        sd_hiddenimports + cv2_hiddenimports + wv_hiddenimports + [
            # pywebview Cocoa backend
            'webview.platforms.cocoa',
            'webview.platforms',
            # pyobjc — screen size + app icon
            'AppKit',
            'Foundation',
            'objc',
            # audio / capture
            'numpy',
            'numpy.core',
            'numpy.core._multiarray_umath',
            'scipy',
            'scipy.io',
            'scipy.io.wavfile',
            'cffi',
            '_cffi_backend',
            # Groq transcription
            'groq',
            'groq._client',
            'groq.resources',
            'groq.resources.audio',
            'groq.resources.audio.transcriptions',
            # stdlib used directly
            'urllib.request',
        ]
    ),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Explicitly exclude backend modules so they are never pulled in
    excludes=[
        'memory', 'brain', 'voice', 'control', 'scripts',
        'flask', 'flask_cors', 'anthropic', 'openai',
        'telegram', 'whatsapp',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='JARVIS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    target_arch='arm64',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='JARVIS',
)

app = BUNDLE(
    coll,
    name='JARVIS.app',
    icon='app/icon.icns',
    bundle_identifier='com.elnatan.jarvis',
    info_plist={
        'CFBundleName': 'JARVIS',
        'CFBundleDisplayName': 'JARVIS',
        'CFBundleIdentifier': 'com.elnatan.jarvis',
        'CFBundleVersion': '1.0',
        'CFBundleShortVersionString': '1.0',
        'NSHighResolutionCapable': True,
        # LSUIElement: the app has no Dock icon — it's the floating bubble
        'LSUIElement': True,
        'LSMinimumSystemVersion': '12.0',
        'NSCameraUsageDescription':
            'JARVIS uses the camera to scan and describe your physical environment.',
        'NSMicrophoneUsageDescription':
            'JARVIS uses the microphone for voice commands and conversation.',
        'NSSpeechRecognitionUsageDescription':
            'JARVIS transcribes your voice so you can speak to it naturally.',
        'NSAppleEventsUsageDescription':
            'JARVIS controls Music, Messages, and other apps on your behalf.',
    },
)
