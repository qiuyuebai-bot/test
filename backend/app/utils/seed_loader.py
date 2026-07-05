"""
种子数据加载器
从 JSON 配置文件读取种子数据，避免在 Python 代码中硬编码业务数据。
"""
import json
from pathlib import Path
from typing import Any, Dict, List

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_seed_data(filename: str) -> List[Dict[str, Any]]:
    """
    读取种子数据 JSON 文件。

    Args:
        filename: 数据文件名（如 "learners.json"）

    Returns:
        记录列表（已剥离 _meta 元信息）

    Raises:
        FileNotFoundError: 数据文件不存在
        ValueError: 文件格式不合法
    """
    path = DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"种子数据文件不存在: {path}")

    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    if not isinstance(payload, dict) or "records" not in payload:
        raise ValueError(f"种子数据文件格式不合法，应包含 'records' 字段: {path}")

    records = payload["records"]
    if not isinstance(records, list):
        raise ValueError(f"'records' 必须是列表: {path}")

    return records


def load_seed_payload(filename: str) -> Dict[str, Any]:
    """
    读取种子数据 JSON 文件并返回完整 payload（含 records 及其他自定义字段）。

    用于在 records 之外还携带 explanations/key_points 等附加配置的场景。

    Args:
        filename: 数据文件名（如 "questions.json"）

    Returns:
        完整 payload dict（含 _meta、records 及其他字段）

    Raises:
        FileNotFoundError: 数据文件不存在
        ValueError: 文件格式不合法
    """
    path = DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"种子数据文件不存在: {path}")

    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    if not isinstance(payload, dict):
        raise ValueError(f"种子数据文件格式不合法，应为 JSON 对象: {path}")

    return payload


def load_seed_meta(filename: str) -> Dict[str, Any]:
    """读取种子数据的 _meta 元信息"""
    path = DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"种子数据文件不存在: {path}")

    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    return payload.get("_meta", {})
