"""校验专家标注 fixture 并计算 rubric §6 交叉验证指标。

校验项：required_fields 完整、标签合法、日期格式、reviewer_id 非空、
case_id 可回查 learning_resources、reference_slice_ids 可回查 knowledge_slices。

交叉验证（rubric §6）：
1. 分档一致率 = mean(高档 supported 占比, 低档 非 supported 占比)
2. 矛盾检出率 = contradicted 条目中系统 hallucination_detected=0 的占比

用法：
    python -m scripts.validate_expert_annotations                  # 校验 + 打印指标
    python -m scripts.validate_expert_annotations --update-rubric  # 校验通过后回写 rubric §6
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal  # noqa: E402
from app.models import KnowledgeSlice, LearningResource  # noqa: E402
from scripts.export_annotation_package import normalize_score, tier_of  # noqa: E402

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "industrial_robotics_expert_annotations.json"
RUBRIC_PATH = Path(__file__).resolve().parents[2] / "docs" / "evidence" / "expert-annotation-rubric.md"
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RUBRIC_TEMPLATE = """（待标注完成后填写）
- 标注条数：N（高档 x / 中档 y / 低档 z）
- 分档一致率：0.xx
- 矛盾检出率：0.xx
- 结论一句话：……"""


def validate_annotations(
    payload: Dict[str, Any],
    resources_by_id: Dict[int, Dict[str, Any]],
    slices_by_id: Dict[int, Dict[str, Any]],
) -> Tuple[List[str], List[str]]:
    """返回 (errors, warnings)。errors 非空即校验失败。"""
    errors: List[str] = []
    warnings: List[str] = []
    annotations = payload.get("annotations", [])
    required_fields = payload.get("required_fields", [])
    allowed_labels = set(payload.get("allowed_labels", []))

    if not annotations:
        errors.append("annotations 为空：尚未回收真实专家标注")
        return errors, warnings

    seen_case_ids = set()
    for index, item in enumerate(annotations):
        where = f"annotations[{index}] (case_id={item.get('case_id', '?')})"
        for field in required_fields:
            if item.get(field) in (None, "", []):
                errors.append(f"{where}: 缺少必填字段 {field}")

        case_id = item.get("case_id", "")
        if case_id in seen_case_ids:
            errors.append(f"{where}: case_id 重复")
        seen_case_ids.add(case_id)

        if not re.fullmatch(r"res_\d+", str(case_id)):
            errors.append(f"{where}: case_id 格式应为 res_<资源ID>")
            continue
        resource_id = int(str(case_id).split("_", 1)[1])
        if resource_id not in resources_by_id:
            errors.append(f"{where}: 资源 {resource_id} 不存在于 learning_resources")
            continue

        label = item.get("expert_label")
        if label not in allowed_labels:
            errors.append(f"{where}: expert_label={label!r} 不在 allowed_labels 内")

        reviewed_at = str(item.get("reviewed_at", ""))
        if reviewed_at and not DATE_PATTERN.match(reviewed_at):
            errors.append(f"{where}: reviewed_at={reviewed_at!r} 应为 YYYY-MM-DD")
        elif reviewed_at:
            try:
                datetime.strptime(reviewed_at, "%Y-%m-%d")
            except ValueError:
                errors.append(f"{where}: reviewed_at={reviewed_at!r} 不是合法日期")

        resource = resources_by_id[resource_id]
        slice_ids = item.get("reference_slice_ids") or []
        missing = [sid for sid in slice_ids if sid not in slices_by_id]
        if missing:
            errors.append(f"{where}: reference_slice_ids 引用了不存在的切片 {missing}")
        if not slice_ids:
            warnings.append(f"{where}: 无参考切片，标签应为 insufficient_evidence")

        resource_slice_ids = set(resource.get("source_slice_ids") or [])
        stray = [sid for sid in slice_ids if sid not in resource_slice_ids]
        if stray:
            warnings.append(f"{where}: 引用切片 {stray} 不在资源 {resource_id} 的 source_slice_ids 内（请确认引用依据）")

        if label == "supported" and resource.get("hallucination_detected"):
            warnings.append(f"{where}: 系统已检出幻觉但专家判 supported，建议复核")

    return errors, warnings


def compute_cross_validation(
    annotations: List[Dict[str, Any]],
    resources_by_id: Dict[int, Dict[str, Any]],
) -> Dict[str, Any]:
    """计算 rubric §6 两项指标；样本不足时对应值为 None（诚实披露）。"""
    tier_labels = {"supported": [], "non_supported": [], "contradicted": []}
    tier_counts = {"high": 0, "mid": 0, "low": 0}
    high_supported = high_total = low_non_supported = low_total = 0
    contradicted_total = contradicted_missed = 0

    for item in annotations:
        try:
            resource_id = int(str(item.get("case_id", "")).split("_", 1)[1])
        except (IndexError, ValueError):
            continue
        resource = resources_by_id.get(resource_id)
        if resource is None:
            continue
        tier = tier_of(normalize_score(resource.get("match_score")))
        tier_counts[tier] += 1
        label = item.get("expert_label")

        if tier == "high":
            high_total += 1
            if label == "supported":
                high_supported += 1
        elif tier == "low":
            low_total += 1
            if label != "supported":
                low_non_supported += 1

        if label == "contradicted":
            contradicted_total += 1
            if not resource.get("hallucination_detected"):
                contradicted_missed += 1

    tier_agreement = (
        round((high_supported / high_total + low_non_supported / low_total) / 2, 3)
        if high_total > 0 and low_total > 0
        else None
    )
    contradiction_detection = (
        round(contradicted_missed / contradicted_total, 3)
        if contradicted_total > 0
        else None
    )
    return {
        "annotation_count": len(annotations),
        "tier_counts": tier_counts,
        "high_tier_supported": f"{high_supported}/{high_total}",
        "low_tier_non_supported": f"{low_non_supported}/{low_total}",
        "tier_agreement": tier_agreement,
        "contradiction_detection": contradiction_detection,
        "contradicted_total": contradicted_total,
        "contradicted_missed_by_system": contradicted_missed,
    }


def render_rubric_section(metrics: Dict[str, Any]) -> str:
    """生成 rubric §6 的指标填报表（替换"（待标注完成后填写）"模板块）。"""
    tier_counts = metrics["tier_counts"]
    agreement = metrics["tier_agreement"]
    detection = metrics["contradiction_detection"]
    agreement_text = "无法计算（高档或低档样本为 0）" if agreement is None else f"{agreement}"
    detection_text = (
        "无法计算（无 contradicted 条目）"
        if detection is None
        else f"{detection}（{metrics['contradicted_missed_by_system']}/{metrics['contradicted_total']}）"
    )
    return f"""- 标注条数：{metrics['annotation_count']}（高档 {tier_counts['high']} / 中档 {tier_counts['mid']} / 低档 {tier_counts['low']}）
- 高档 supported：{metrics['high_tier_supported']}；低档非 supported：{metrics['low_tier_non_supported']}
- 分档一致率：{agreement_text}
- 矛盾检出率：{detection_text}
- 结论一句话：由 validate_expert_annotations.py 于 {datetime.now().strftime('%Y-%m-%d %H:%M')} 依据 fixture 自动计算。"""


def update_rubric(metrics: Dict[str, Any]) -> bool:
    """把 §6 模板块替换为计算结果；找不到锚点时返回 False。"""
    if not RUBRIC_PATH.exists():
        return False
    text = RUBRIC_PATH.read_text(encoding="utf-8")
    if RUBRIC_TEMPLATE not in text:
        return False
    text = text.replace(RUBRIC_TEMPLATE, render_rubric_section(metrics))
    RUBRIC_PATH.write_text(text, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update-rubric", action="store_true", help="校验通过后回写 rubric §6")
    args = parser.parse_args()

    if not FIXTURE_PATH.exists():
        print(f"错误：fixture 不存在：{FIXTURE_PATH}")
        return 1

    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    annotations = payload.get("annotations", [])

    db = SessionLocal()
    try:
        resource_ids = {
            int(str(item.get("case_id", "")).split("_", 1)[1])
            for item in annotations
            if re.fullmatch(r"res_\d+", str(item.get("case_id", "")))
        }
        resources_by_id = {}
        if resource_ids:
            rows = db.query(LearningResource).filter(LearningResource.id.in_(resource_ids)).all()
            resources_by_id = {
                r.id: {
                    "source_slice_ids": r.source_slice_ids or [],
                    "match_score": r.match_score,
                    "hallucination_detected": r.hallucination_detected,
                }
                for r in rows
            }
        slice_ids = {sid for item in annotations for sid in (item.get("reference_slice_ids") or [])}
        slices_by_id = {}
        if slice_ids:
            rows = db.query(KnowledgeSlice).filter(KnowledgeSlice.id.in_(slice_ids)).all()
            slices_by_id = {r.id: {"title": r.title} for r in rows}
    finally:
        db.close()

    errors, warnings = validate_annotations(payload, resources_by_id, slices_by_id)

    print(f"fixture：{FIXTURE_PATH}")
    print(f"标注条数：{len(annotations)}")
    if errors:
        print("\n校验失败：")
        for message in errors:
            print(f"  [error] {message}")
        return 1
    if warnings:
        print("\n警告：")
        for message in warnings:
            print(f"  [warn] {message}")

    print("\n校验通过。")
    if annotations:
        metrics = compute_cross_validation(annotations, resources_by_id)
        print("交叉验证指标（rubric §6）：")
        print(f"  分档一致率：{metrics['tier_agreement']}")
        print(f"  矛盾检出率：{metrics['contradiction_detection']}")
        print(f"  分档分布：{metrics['tier_counts']}")
        if args.update_rubric:
            if update_rubric(metrics):
                print(f"\n已回写 rubric §6：{RUBRIC_PATH}")
            else:
                print("\n警告：rubric §6 模板锚点未找到，未回写（可能已填写过）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
