# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 规格：将 FastAPI 后端和运行必需资源制作成独立目录包。"""
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules


ROOT = Path(SPECPATH).resolve().parent
BACKEND = ROOT / "backend"

datas = [
    (str(BACKEND / "alembic.ini"), "."),
    (str(BACKEND / "alembic"), "alembic"),
    (str(BACKEND / "app" / "data"), "app/data"),
    # 业务生成、审核和导学依赖磁盘上的提示词模板；连接测试不会读取它们。
    (str(BACKEND / "app" / "prompts"), "app/prompts"),
]

# Chroma、令牌器和嵌入模型的 Python/动态资源在桌面离线降级与正常模式间共用。
for package in ("chromadb", "tiktoken", "sentence_transformers", "transformers", "tokenizers"):
    try:
        datas.extend(collect_data_files(package))
        datas.extend(collect_dynamic_libs(package))
    except Exception:
        pass

hiddenimports = collect_submodules("app")
hiddenimports.extend([
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
])

analysis = Analysis(
    [str(BACKEND / "desktop_entry.py")],
    pathex=[str(BACKEND)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "tests", "playwright"],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.zipfiles,
    analysis.datas,
    [],
    name="zhiyu-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.zipfiles,
    analysis.datas,
    strip=False,
    upx=False,
    name="backend",
)
