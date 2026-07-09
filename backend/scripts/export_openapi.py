#!/usr/bin/env python3
"""导出 FastAPI OpenAPI 规范为静态 JSON 文件

使用方式：
    # 导出 openapi.json 到 docs/api/
    python scripts/export_openapi.py

    # 仅校验 OpenAPI 可正常生成，不写文件（CI 用）
    python scripts/export_openapi.py --check

输出：
    docs/api/openapi.json  （相对项目根目录）

用途：
    - CI 中校验 OpenAPI 规范可正常生成，防止路由/schema 定义错误
    - 生成静态 JSON 供 Swagger UI / Redoc 离线托管
    - 版本化 API 规范，便于前端联调与第三方对接
"""
import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

OUTPUT_PATH = PROJECT_ROOT / "docs" / "api" / "openapi.json"


def export_openapi() -> dict:
    from app.main import app
    return app.openapi()


def main() -> int:
    parser = argparse.ArgumentParser(description="导出 FastAPI OpenAPI 规范")
    parser.add_argument(
        "--check",
        action="store_true",
        help="仅校验 OpenAPI 可生成，不写文件（CI 模式）",
    )
    args = parser.parse_args()

    try:
        schema = export_openapi()
    except Exception as e:
        print(f"[FAIL] OpenAPI 生成失败: {e}", file=sys.stderr)
        return 1

    path_count = len(schema.get("paths", {}))
    schema_count = len(schema.get("components", {}).get("schemas", {}))
    tag_count = len(schema.get("tags", []))

    print(f"[OK] OpenAPI 生成成功")
    print(f"  标题:   {schema.get('info', {}).get('title', 'N/A')}")
    print(f"  版本:   {schema.get('info', {}).get('version', 'N/A')}")
    print(f"  路径数: {path_count}")
    print(f"  模型数: {schema_count}")
    print(f"  标签数: {tag_count}")

    if args.check:
        print("[CHECK] --check 模式，跳过文件写入")
        return 0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[WRITE] 已写入 {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
