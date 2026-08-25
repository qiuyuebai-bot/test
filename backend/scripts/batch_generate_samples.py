"""批量生成指标样本：通过完整 Agent 流水线生成 50+ 组资源。

用法:
  cd backend
  python -m scripts.batch_generate_samples --limit 1   # 冒烟测试
  python -m scripts.batch_generate_samples             # 全量执行

每次 run_full_pipeline 产出:
  - 1 条 LearningResource (match_score, source=agent_generation_pipeline)
  - 1-3 条 DebateRecord (幻觉率样本)
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal  # noqa: E402
import app.utils.llm  # noqa: E402,F401  # 先行加载以打破 utils<->ai_content_service 循环导入
from app.agents.orchestrator import AgentOrchestrator  # noqa: E402
from app.models import LearnerProfile, KnowledgeDoc  # noqa: E402

INDUSTRY_FALLBACK = {
    "人工智能": "人工智能训练",
    "智能制造": "智能制造",
    "工业互联网": "工业互联网",
}


def build_matrix(db) -> list[tuple[int, str, str, str]]:
    """学习者 × 主题 矩阵：每个学习者取其行业 + 通用行业的文档标题作为主题。"""
    learners = db.query(LearnerProfile).order_by(LearnerProfile.id).all()
    docs = db.query(KnowledgeDoc).filter(KnowledgeDoc.is_enabled == True).all()  # noqa: E712
    by_industry: dict[str, list[str]] = {}
    for d in docs:
        by_industry.setdefault(d.industry or "通用", []).append(d.title)

    matrix = []
    for learner in learners:
        raw = learner.target_industry or "通用"
        industry = INDUSTRY_FALLBACK.get(raw, raw)
        # 本行业文档标题 + 通用文档标题作为主题池
        topics = list(by_industry.get(industry, [])) + list(by_industry.get("通用", []))
        for topic in topics:
            label = learner.display_name or learner.real_name or f"learner_{learner.id}"
            matrix.append((learner.id, label, industry, topic))
    return matrix


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="限制运行数量（冒烟测试用）")
    parser.add_argument("--resource-type", default="guide", help="资源类型")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        matrix = build_matrix(db)
    finally:
        db.close()

    total = len(matrix)
    plan = matrix[: args.limit] if args.limit else matrix
    print(f"矩阵规模: {total} 组 (学习者×主题)，本次执行 {len(plan)} 组")
    if not plan:
        print("矩阵为空，退出")
        return 1

    orchestrator = AgentOrchestrator()
    ok, failed = 0, 0
    start = time.time()
    for i, (learner_id, learner_name, industry, topic) in enumerate(plan, 1):
        task = orchestrator.task_repo.create_task(
            learner_id=learner_id,
            task_name=f"批量样本生成: {topic[:20]}",
            task_type="full_pipeline",
            input_data={"target_topic": topic, "industry": industry, "resource_type": args.resource_type},
        )
        task_id = task["task_id"]
        t0 = time.time()
        try:
            result = orchestrator.run_full_pipeline(
                task_id=task_id,
                learner_id=learner_id,
                target_topic=topic,
                resource_type=args.resource_type,
                industry=industry,
            )
            status = result.get("status", "unknown")
            ms = result.get("match_score")
            dur = time.time() - t0
            print(f"[{i}/{len(plan)}] learner={learner_id} ({learner_name}) topic={topic[:24]} -> {status}, match_score={ms}, {dur:.1f}s", flush=True)
            ok += 1
        except Exception as exc:
            dur = time.time() - t0
            print(f"[{i}/{len(plan)}] learner={learner_id} topic={topic[:24]} -> FAILED: {exc} ({dur:.1f}s)", flush=True)
            failed += 1

    total_dur = time.time() - start
    print(f"\n完成: 成功 {ok}, 失败 {failed}, 总耗时 {total_dur:.0f}s, 平均 {total_dur / max(1, ok + failed):.1f}s/组")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
