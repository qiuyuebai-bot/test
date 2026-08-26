"""按分档抽样导出专家标注包（HTML 对照材料 + 空白标注 CSV）。

对应 docs/evidence/expert-annotation-rubric.md §1/§4：高/中/低三档抽样，
评审员在 HTML 包中并排对照"生成内容 vs 参考切片原文"逐条打标，标注结果
填入 CSV，回填 fixture 后由 validate_expert_annotations.py 校验与交叉验证。

match_score 刻意不出现在标注材料中（盲标），避免锚定偏差。

用法：
    python -m scripts.export_annotation_package                    # 每档 5 条
    python -m scripts.export_annotation_package --per-tier 7       # 每档 7 条
    python -m scripts.export_annotation_package --output-dir docs/evidence
"""
import argparse
import csv
import html
import io
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal  # noqa: E402
from app.models import KnowledgeSlice, LearningResource  # noqa: E402

TIER_LABELS = {"high": "高档（match_score ≥ 80）", "mid": "中档（60 ≤ match_score < 80）", "low": "低档（match_score < 60，含 NULL）"}
LABEL_GUIDE = [
    ("supported", "论断有源、数值单位合规、无主题混淆、无安全违规表述"),
    ("contradicted", "与参考切片直接矛盾 / 触发高危行业规则 / 数值单位错误"),
    ("insufficient_evidence", "参考切片未覆盖论断范围，既不能确认也不能证伪（诚实标签）"),
]


def normalize_score(raw: Any) -> Optional[float]:
    """match_score 兼容 0~1 与 0~100 两种存储，统一为百分制。"""
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if 0 <= value <= 1:
        return round(value * 100, 2)
    return round(value, 2)


def tier_of(score: Optional[float]) -> str:
    if score is None or score < 60:
        return "low"
    if score < 80:
        return "mid"
    return "high"


def build_cases(
    resources: List[Dict[str, Any]],
    slices_by_id: Dict[int, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """把资源行与参考切片组装成标注用例（不含 match_score）。"""
    cases = []
    for res in resources:
        slice_ids = list(res.get("source_slice_ids") or [])
        references = [
            {
                "slice_id": sid,
                "title": (slices_by_id.get(sid) or {}).get("title", "（切片不存在）"),
                "content": (slices_by_id.get(sid) or {}).get("content", "（切片不存在，倾向 insufficient_evidence）"),
            }
            for sid in slice_ids
        ]
        cases.append({
            "case_id": f"res_{res['id']}",
            "resource_id": res["id"],
            "topic": res.get("knowledge_topic") or res.get("title") or "",
            "resource_title": res.get("title") or "",
            "resource_type": res.get("resource_type") or "",
            "content": res.get("content") or "",
            "tier": tier_of(normalize_score(res.get("match_score"))),
            "has_reference": bool(references),
            "references": references,
        })
    return cases


def _render_label_guide() -> str:
    rows = "\n".join(
        f"<tr><td><code>{html.escape(label)}</code></td><td>{html.escape(desc)}</td></tr>"
        for label, desc in LABEL_GUIDE
    )
    return (
        "<p><strong>标签定义（详见 expert-annotation-rubric.md）：</strong></p>"
        f"<table class='guide'><tr><th>标签</th><th>判定要点</th></tr>{rows}</table>"
    )


def render_html(cases: List[Dict[str, Any]], generated_at: str) -> str:
    """自包含 HTML 标注包：左列生成内容、右列参考切片原文并排对照。"""
    cards = []
    for case in cases:
        refs = "\n".join(
            f"<div class='slice'><div class='slice-title'>[{html.escape(str(r['slice_id']))}] {html.escape(r['title'])}</div>"
            f"<pre>{html.escape(r['content'])}</pre></div>"
            for r in case["references"]
        ) or "<div class='slice missing'>（无参考切片，倾向 insufficient_evidence）</div>"
        tier_note = "" if case["has_reference"] else "<span class='warn'>无溯源切片</span>"
        cards.append(f"""
<section class="case">
  <header>
    <span class="case-id">{html.escape(case['case_id'])}</span>
    <span class="topic">{html.escape(case['topic'])}</span>
    <span class="meta">{html.escape(case['resource_type'])} {tier_note}</span>
  </header>
  <div class="columns">
    <div class="col generated"><h3>生成内容</h3><pre>{html.escape(case['content'])}</pre></div>
    <div class="col reference"><h3>参考切片原文</h3>{refs}</div>
  </div>
</section>""")

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>工业机器人领域专家标注包</title>
<style>
  body {{ font-family: "Segoe UI", "Microsoft YaHei", sans-serif; margin: 0; background: #f5f6f8; color: #1f2933; }}
  .banner {{ background: #1f2933; color: #fff; padding: 20px 28px; }}
  .banner h1 {{ margin: 0 0 6px; font-size: 20px; }}
  .banner p {{ margin: 0; color: #9fb3c8; font-size: 13px; }}
  main {{ padding: 20px 28px; }}
  .guide {{ border-collapse: collapse; margin: 12px 0 4px; background: #fff; }}
  .guide th, .guide td {{ border: 1px solid #d9e2ec; padding: 6px 12px; font-size: 13px; text-align: left; }}
  .guide th {{ background: #f0f4f8; }}
  .case {{ background: #fff; border: 1px solid #d9e2ec; border-radius: 8px; margin: 18px 0; overflow: hidden; }}
  .case header {{ display: flex; gap: 14px; align-items: center; padding: 10px 16px; background: #f0f4f8; border-bottom: 1px solid #d9e2ec; }}
  .case-id {{ font-weight: 700; font-family: Consolas, monospace; }}
  .topic {{ font-size: 14px; }}
  .meta {{ margin-left: auto; font-size: 12px; color: #627d98; }}
  .warn {{ color: #b54708; font-weight: 600; }}
  .columns {{ display: grid; grid-template-columns: 1fr 1fr; }}
  .col {{ padding: 12px 16px; }}
  .col.generated {{ border-right: 1px solid #d9e2ec; }}
  .col h3 {{ margin: 4px 0 8px; font-size: 13px; color: #486581; }}
  pre {{ white-space: pre-wrap; word-break: break-word; font-family: inherit; font-size: 13px; line-height: 1.7; margin: 0; max-height: 520px; overflow-y: auto; }}
  .slice {{ margin-bottom: 12px; }}
  .slice-title {{ font-weight: 600; font-size: 13px; margin-bottom: 4px; }}
  .slice.missing {{ color: #b54708; }}
  @media print {{ .case {{ break-inside: avoid; }} }}
</style>
</head>
<body>
<div class="banner">
  <h1>工业机器人领域专家标注包</h1>
  <p>生成时间 {html.escape(generated_at)} · 共 {len(cases)} 条 · 标签三选一：supported / contradicted / insufficient_evidence · 系统匹配分已隐藏（盲标）</p>
</div>
<main>
{_render_label_guide()}
{''.join(cards)}
</main>
</body>
</html>"""


def render_csv(cases: List[Dict[str, Any]]) -> str:
    """空白标注表：评审员只填 expert_label / reviewer_id / reviewed_at / notes。"""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["case_id", "topic", "reference_slice_ids", "expert_label", "reviewer_id", "reviewed_at", "notes"])
    for case in cases:
        slice_ids = ";".join(str(r["slice_id"]) for r in case["references"])
        writer.writerow([case["case_id"], case["topic"], slice_ids, "", "", "", ""])
    return buffer.getvalue()


def sample_resources(db, per_tier: int) -> List[LearningResource]:
    """按 rubric §1 分档抽样：高档取分最高，中/低档按 id 稳定排序。"""
    enabled = db.query(LearningResource).filter(LearningResource.is_enabled == True).all()  # noqa: E712
    buckets: Dict[str, List[LearningResource]] = {"high": [], "mid": [], "low": []}
    for res in enabled:
        buckets[tier_of(normalize_score(res.match_score))].append(res)
    buckets["high"].sort(key=lambda r: normalize_score(r.match_score) or 0, reverse=True)
    for key in ("mid", "low"):
        buckets[key].sort(key=lambda r: r.id)
    sampled = [r for key in ("high", "mid", "low") for r in buckets[key][:per_tier]]
    return sampled


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-tier", type=int, default=5, help="每档抽样条数（默认 5）")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[2] / "docs" / "evidence")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        resources = sample_resources(db, args.per_tier)
        slice_ids = sorted({sid for r in resources for sid in (r.source_slice_ids or [])})
        slices = {
            s.id: {"title": s.title or "", "content": s.content or ""}
            for s in db.query(KnowledgeSlice).filter(KnowledgeSlice.id.in_(slice_ids))
        } if slice_ids else {}
        resource_rows = [
            {
                "id": r.id,
                "title": r.title,
                "knowledge_topic": r.knowledge_topic,
                "resource_type": r.resource_type,
                "content": r.content,
                "match_score": r.match_score,
                "source_slice_ids": r.source_slice_ids or [],
            }
            for r in resources
        ]
    finally:
        db.close()

    cases = build_cases(resource_rows, slices)
    tier_counts = {key: sum(1 for c in cases if c["tier"] == key) for key in ("high", "mid", "low")}
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    from datetime import datetime

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    html_path = output_dir / "annotation-package.html"
    csv_path = output_dir / "annotation-sheet.csv"
    html_path.write_text(render_html(cases, generated_at), encoding="utf-8")
    csv_path.write_text("\ufeff" + render_csv(cases), encoding="utf-8")  # BOM 便于 Excel 打开中文

    print(f"标注包导出完成：{len(cases)} 条")
    for key in ("high", "mid", "low"):
        print(f"  {TIER_LABELS[key]}：{tier_counts[key]} 条")
    print(f"  HTML 对照材料：{html_path}")
    print(f"  空白标注表：{csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
