"""桌面发行包的路径解析与运行环境帮助函数。"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def bundle_path(relative: str) -> Path:
    """返回源码目录或 PyInstaller 冻结目录内的只读资源路径。"""
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("冻结资源路径必须是包内相对路径")
    backend_root = Path(__file__).resolve().parents[1]
    root = Path(getattr(sys, "_MEIPASS", backend_root))
    return (root / path).resolve()


def desktop_data_dir() -> Path:
    """返回桌面模式的数据目录；源码模式继续使用项目根目录 data。"""
    configured = os.environ.get("APP_DATA_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "data"


def desktop_web_dir() -> Path | None:
    """读取 Electron 注入的前端构建目录，未配置时不注册静态页面。"""
    configured = os.environ.get("DESKTOP_WEB_DIR", "").strip()
    return Path(configured).expanduser().resolve() if configured else None
