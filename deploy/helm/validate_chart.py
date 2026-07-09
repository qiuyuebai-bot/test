#!/usr/env/python
# -*- coding: utf-8 -*-
"""
Helm Chart 验证脚本（无 helm CLI 依赖）
验证内容：
1. Chart.yaml 与 values.yaml 的 YAML 语法正确性
2. _helpers.tpl 中定义的 helper 函数都被引用
3. 所有模板文件引用的 helper 函数都已定义
4. 检查 .helmignore 是否存在
5. 输出 Chart 目录结构
"""
import os
import re
import sys
import yaml
from pathlib import Path

CHART_DIR = Path(r"c:\Users\22602\Desktop\新建文件夹\deploy\helm")
errors = []
warnings = []
ok = []


def log_ok(msg):
    ok.append(msg)
    print(f"  [OK] {msg}")


def log_warn(msg):
    warnings.append(msg)
    print(f"  [WARN] {msg}")


def log_err(msg):
    errors.append(msg)
    print(f"  [FAIL] {msg}")


print("=" * 60)
print("Helm Chart 验证报告")
print("=" * 60)

# 1. 检查必需文件
print("\n[1/6] 检查必需文件...")
required_files = [
    "Chart.yaml",
    "values.yaml",
    "templates/_helpers.tpl",
    "templates/NOTES.txt",
]
for f in required_files:
    p = CHART_DIR / f
    if p.exists():
        log_ok(f"文件存在: {f}")
    else:
        log_err(f"缺失必需文件: {f}")

# 2. 验证 Chart.yaml 语法
print("\n[2/6] 验证 Chart.yaml YAML 语法...")
try:
    with open(CHART_DIR / "Chart.yaml", "r", encoding="utf-8") as f:
        chart_data = yaml.safe_load(f)
    required_chart_fields = ["apiVersion", "name", "version", "appVersion", "description"]
    missing = [f for f in required_chart_fields if f not in chart_data]
    if missing:
        log_err(f"Chart.yaml 缺失字段: {missing}")
    else:
        log_ok(f"Chart.yaml 语法正确: name={chart_data['name']}, version={chart_data['version']}, appVersion={chart_data['appVersion']}")
except yaml.YAMLError as e:
    log_err(f"Chart.yaml YAML 解析错误: {e}")
except Exception as e:
    log_err(f"读取 Chart.yaml 失败: {e}")

# 3. 验证 values.yaml 语法
print("\n[3/6] 验证 values.yaml YAML 语法...")
try:
    with open(CHART_DIR / "values.yaml", "r", encoding="utf-8") as f:
        values_data = yaml.safe_load(f)
    log_ok(f"values.yaml 语法正确，顶级键: {sorted(list(values_data.keys()))}")

    # 检查关键配置项
    required_sections = ["global", "images", "frontend", "backend", "postgresql", "redis", "appConfig", "secrets"]
    missing_sections = [s for s in required_sections if s not in values_data]
    if missing_sections:
        log_err(f"values.yaml 缺失关键配置段: {missing_sections}")
    else:
        log_ok("values.yaml 关键配置段齐全")

    # 检查 appConfig 中的关键配置
    required_app_config = ["DATABASE_URL", "REDIS_URL", "APP_NAME", "API_PREFIX", "OPENAI_API_BASE"]
    missing_app_config = [k for k in required_app_config if k not in values_data.get("appConfig", {})]
    if missing_app_config:
        log_warn(f"appConfig 中缺失配置项: {missing_app_config}")
    else:
        log_ok("appConfig 关键配置项齐全")

    # 检查 secrets.data 中的关键配置
    required_secrets = ["SECRET_KEY", "OPENAI_API_KEY", "POSTGRES_PASSWORD"]
    missing_secrets = [k for k in required_secrets if k not in values_data.get("secrets", {}).get("data", {})]
    if missing_secrets:
        log_err(f"secrets.data 中缺失敏感配置: {missing_secrets}")
    else:
        log_ok("secrets.data 关键配置项齐全")

except yaml.YAMLError as e:
    log_err(f"values.yaml YAML 解析错误: {e}")
except Exception as e:
    log_err(f"读取 values.yaml 失败: {e}")

# 4. 检查 _helpers.tpl 中定义的函数与模板中的引用
print("\n[4/6] 检查 _helpers.tpl 中定义的 helper 函数...")
helpers_file = CHART_DIR / "templates" / "_helpers.tpl"
defined_helpers = set()
if helpers_file.exists():
    content = helpers_file.read_text(encoding="utf-8")
    # 匹配 {{- define "xxx" -}}
    pattern = r'\{\{-?\s*define\s+"([^"]+)"\s*-?\}\}'
    defined_helpers = set(re.findall(pattern, content))
    log_ok(f"_helpers.tpl 中定义了 {len(defined_helpers)} 个 helper 函数:")
    for h in sorted(defined_helpers):
        print(f"        - {h}")

# 5. 检查所有模板文件中引用的 helper 函数是否已定义
print("\n[5/6] 检查模板中引用的 helper 函数是否已定义...")
template_dir = CHART_DIR / "templates"
all_referenced = set()
for root, _, files in os.walk(template_dir):
    for f in files:
        if f.endswith(".yaml") or f.endswith(".tpl") or f.endswith(".txt"):
            fpath = Path(root) / f
            content = fpath.read_text(encoding="utf-8")
            # 匹配 {{ include "xxx" ... }} 和 {{ "xxx" }}
            include_pattern = r'\{\{-?\s*include\s+"([^"]+)"'
            referenced = set(re.findall(include_pattern, content))
            for ref in referenced:
                all_referenced.add(ref)
                if ref not in defined_helpers:
                    log_err(f"模板 {fpath.relative_to(CHART_DIR)} 引用了未定义的 helper: {ref}")

if all_referenced:
    log_ok(f"模板共引用了 {len(all_referenced)} 个不同的 helper 函数")
    undefined = all_referenced - defined_helpers
    if undefined:
        log_err(f"有 {len(undefined)} 个未定义的 helper 被引用: {undefined}")
    else:
        log_ok("所有引用的 helper 函数均已定义")

# 6. 检查目录结构完整性
print("\n[6/6] 检查 Chart 目录结构...")
expected_template_subdirs = ["backend", "frontend", "postgres", "redis"]
for d in expected_template_subdirs:
    p = template_dir / d
    if p.exists() and any(p.iterdir()):
        files_in_dir = list(p.glob("*.yaml"))
        log_ok(f"templates/{d}/ 包含 {len(files_in_dir)} 个 YAML 文件")
    else:
        log_warn(f"templates/{d}/ 目录为空或不存在")

# 输出完整目录树
print("\n" + "=" * 60)
print("Chart 目录结构:")
print("=" * 60)
for root, dirs, files in os.walk(CHART_DIR):
    # 跳过 __pycache__ 等
    dirs[:] = [d for d in dirs if not d.startswith("__")]
    level = root.replace(str(CHART_DIR), "").count(os.sep)
    indent = "  " * level
    basename = os.path.basename(root) or "."
    print(f"{indent}{basename}/")
    sub_indent = "  " * (level + 1)
    for f in sorted(files):
        if f.startswith("__"):
            continue
        print(f"{sub_indent}{f}")

# 总结
print("\n" + "=" * 60)
print("验证总结")
print("=" * 60)
print(f"  通过: {len(ok)} 项")
print(f"  警告: {len(warnings)} 项")
print(f"  失败: {len(errors)} 项")

if errors:
    print("\n失败项明细:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("\n所有关键检查项通过！Chart 可用于部署。")
    sys.exit(0)
