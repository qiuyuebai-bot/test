# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 规格：将 FastAPI 后端和运行必需资源制作成独立目录包。"""
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


ROOT = Path(SPECPATH).resolve().parent
BACKEND = ROOT / "backend"

datas = [
    (str(BACKEND / "alembic.ini"), "."),
    (str(BACKEND / "alembic"), "alembic"),
    (str(BACKEND / "app" / "data"), "app/data"),
    # 业务生成、审核和导学依赖磁盘上的提示词模板；连接测试不会读取它们。
    (str(BACKEND / "app" / "prompts"), "app/prompts"),
]

# Chroma 与本地嵌入模型属于可选增强能力。未打入桌面包时，知识库会自动
# 降级为 SQLite 关键词检索；不收集其大型模型运行时以确保 CI 可稳定打包。

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
