"""真实流程扩充答题有效样本（评分项③）。

每个种子学习者走完整真实服务流程，两种模式：

  adaptive（默认，复刻前端 useGuidanceSession.ts 的自适应会话）：
    首题 difficulty=None（诊断推荐难度，question_count=1）
    -> 每答一题取 result.next_question_difficulty 生成下一题
    答错 -> simplify -> 难度降级；答对 -> advance/consolidate -> 升/平。

  round：每轮批量出题；可用 --question-difficulty 固定评估难度。

作答模拟规则（透明可复现，固定随机种子）：
  - 主题相关维度能力分 ability（无映射维度时用六维均值）
  - 题目需求 demand = difficulty * 20
  - 正确概率 p = clamp(0.5 + (ability - demand) / 100, 0.05, 0.95)
  - 按概率答对（提交 answer_key），否则提交一个错误选项
  - 答错后下一题难度由服务端 simplify 决策降级（Task 3 Fix A），低难度下
    正确概率自然回升——这正是自适应闭环应呈现的行为，不是注水。

用法:
  cd backend
  python -m scripts.generate_answer_samples --smoke          # 冒烟：1 学习者 1 主题 2 题
  python -m scripts.generate_answer_samples                  # 全量（adaptive 会话）
"""
import argparse
import hashlib
import random
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal  # noqa: E402
import app.utils.llm  # noqa: E402,F401  # 先行加载以打破 utils<->ai_content_service 循环导入
from app.models import (  # noqa: E402
    AnswerRecord,
    IssuedTutoringQuestion,
    LearnerProfile,
    LearningResource,
)
from app.services.tutoring_service import AdaptiveTutoringService  # noqa: E402

# 与 tutoring_service._update_learner_profile 的主题->维度映射保持一致
TOPIC_DIMENSION = {
    "理论": "theoretical_foundation",
    "编程": "programming_ability",
    "算法": "algorithm_design",
    "架构": "system_architecture",
    "数据": "data_analysis",
    "工程": "engineering_practice",
}

ABILITY_DIMENSIONS = tuple(TOPIC_DIMENSION.values())


def topic_ability(learner: LearnerProfile, topic: str) -> float:
    """取主题相关维度能力分；主题不含关键词时用六维均值。"""
    for keyword, dimension in TOPIC_DIMENSION.items():
        if keyword in (topic or ""):
            return float(getattr(learner, dimension) or 50.0)
    values = [float(getattr(learner, d) or 50.0) for d in ABILITY_DIMENSIONS]
    return sum(values) / len(values)


def correctness_probability(ability: float, difficulty: int) -> float:
    """能力分 vs 题目难度 -> 正确概率（线性映射，边界夹紧）。"""
    demand = int(difficulty) * 20
    return max(0.05, min(0.95, 0.5 + (ability - demand) / 100.0))


def pick_answer(
    answer_key: List[str],
    option_count: int,
    intended_correct: bool,
    rng: random.Random,
) -> List[str]:
    """按意图构造提交答案：答对提交 answer_key，答错提交一个不同的选项组合。"""
    letters = [chr(65 + i) for i in range(option_count)]
    if intended_correct:
        return list(answer_key)
    key_set = set(answer_key)
    if len(letters) - len(key_set) >= 1 and rng.random() < 0.7:
        # 干扰项式错误：多选漏选一个正确项 / 单选选错误项
        wrong_pool = [c for c in letters if c not in key_set]
        return [rng.choice(wrong_pool)] if wrong_pool else letters[:1]
    # 随机错误组合（保证与答案不同）
    for _ in range(10):
        size = rng.randint(1, max(1, len(letters) - 1))
        candidate = rng.sample(letters, size)
        if set(candidate) != key_set:
            return sorted(candidate)
    return [c for c in letters if c not in key_set] or letters[:1]


def load_topics(learner: LearnerProfile, max_topics: int) -> List[str]:
    """推荐主题：primary + alternatives，去重保序。"""
    try:
        rec = AdaptiveTutoringService.get_recommendations(learner.id)
    except Exception as exc:
        print(f"  [warn] 获取推荐失败（learner={learner.id}）: {exc}")
        return []
    topics: List[str] = []
    primary = rec.get("primary_topic")
    if primary:
        topics.append(primary)
    for alt in rec.get("alternatives", []) or []:
        topic = alt.get("topic") if isinstance(alt, dict) else None
        if topic and topic not in topics:
            topics.append(topic)
    return topics[:max_topics]


def answer_one(
    db,
    learner: LearnerProfile,
    topic: str,
    difficulty: Optional[int],
    rng: random.Random,
    stats: Dict[str, int],
    *,
    session_id: Optional[str] = None,
    sequence_index: Optional[int] = None,
) -> Optional[int]:
    """生成并作答一道题；返回服务端给出的下一题难度（闭环信号）。"""
    questions = AdaptiveTutoringService.generate_dynamic_questions(
        user_id=learner.user_id,
        learner_id=learner.id,
        topic=topic,
        difficulty=difficulty,  # None -> 诊断推荐难度；否则严格按指定难度
        question_count=1,
        replace_pending=True,
        session_id=session_id,
    )
    if not questions or not str(questions[0].get("id", "")).isdigit():
        print(f"  [warn] 未生成题目: learner={learner.id} topic={topic}", flush=True)
        return None
    row = (
        db.query(IssuedTutoringQuestion)
        .filter(IssuedTutoringQuestion.id == int(questions[0]["id"]))
        .first()
    )
    if row is None:
        return None
    db.refresh(learner)
    ability = topic_ability(learner, row.topic)
    p = correctness_probability(ability, row.difficulty)
    intended_correct = rng.random() < p
    submit = pick_answer(row.answer_key or [], len(row.options or []), intended_correct, rng)
    t0 = time.time()
    result = AdaptiveTutoringService.process_answer(
        user_id=learner.user_id,
        learner_id=learner.id,
        question_id=str(row.id),
        user_answer=",".join(submit),
        time_spent_ms=rng.randint(15000, 90000),
        hints_used=0,
        session_id=session_id,
        sequence_index=sequence_index,
    )
    dur = time.time() - t0
    if not result.get("success"):
        print(f"  [error] 提交失败 q={row.id}: {result.get('error')}", flush=True)
        stats["failed"] += 1
        return None
    stats["answered"] += 1
    actual_correct = bool(result.get("is_correct"))
    stats["correct"] += 1 if actual_correct else 0
    stats["intent_match"] += 1 if actual_correct == intended_correct else 0
    record = db.query(AnswerRecord).filter(AnswerRecord.id == result.get("answer_record_id")).first()
    with_resource = record is not None and record.next_resource_id is not None
    if with_resource:
        stats["with_resource"] += 1
    decision = result.get("agent_decision", {}).get("decision", "?")
    next_difficulty = result.get("next_question_difficulty")
    print(
        f"  q={row.id} topic={row.topic[:10]} d={row.difficulty} "
        f"p={p:.2f} -> {'对' if actual_correct else '错'} 决策={decision} "
        f"下一题d={next_difficulty} 资源推荐={'是' if with_resource else '否'} ({dur:.1f}s)",
        flush=True,
    )
    return next_difficulty


def run_adaptive_session(
    db,
    learner: LearnerProfile,
    topic: str,
    session_len: int,
    rng: random.Random,
    stats: Dict[str, int],
    session_id: str,
) -> None:
    """复刻前端自适应会话：首题走诊断推荐，之后逐题消费 next_question_difficulty。"""
    next_difficulty: Optional[int] = None
    for sequence_index in range(1, session_len + 1):
        next_difficulty = answer_one(
            db,
            learner,
            topic,
            next_difficulty,
            rng,
            stats,
            session_id=session_id,
            sequence_index=sequence_index,
        )
        if next_difficulty is None:
            break


def run_round(
    db,
    learner: LearnerProfile,
    topic: str,
    per_round: int,
    rng: random.Random,
    stats: Dict[str, int],
    session_id: Optional[str] = None,
    question_difficulty: Optional[int] = None,
) -> None:
    """批量出题一轮；未指定难度时走诊断推荐难度。"""
    for sequence_index in range(1, per_round + 1):
        if answer_one(
            db,
            learner,
            topic,
            question_difficulty,
            rng,
            stats,
            session_id=session_id,
            sequence_index=sequence_index,
        ) is None:
            break


def _session_id(mode: str, learner_id: int, topic: str, seed: int) -> str:
    topic_key = hashlib.sha1(topic.encode("utf-8")).hexdigest()[:10]
    return f"sample_{mode}_s{seed}_l{learner_id}_t{topic_key}"


def run_learner(
    db,
    learner: LearnerProfile,
    mode: str,
    session_len: int,
    max_topics: int,
    rng: random.Random,
    seed: int,
    question_difficulty: Optional[int] = None,
) -> Dict[str, int]:
    label = learner.display_name or learner.real_name or f"learner_{learner.id}"
    low_res = (
        db.query(LearningResource)
        .filter(LearningResource.learner_id == learner.id, LearningResource.difficulty_level <= 2)
        .count()
    )
    print(f"\n=== learner={learner.id} ({label}) 行业={learner.target_industry} 低难度资源={low_res} 模式={mode} ===", flush=True)
    stats = {"answered": 0, "correct": 0, "with_resource": 0, "intent_match": 0, "failed": 0}
    topics = load_topics(learner, max_topics)
    if not topics:
        print("  [warn] 无可用主题，跳过")
        return stats
    print(f"  主题: {topics}", flush=True)
    for topic in topics:
        db.refresh(learner)
        print(f"  -- 会话 topic={topic} 能力={topic_ability(learner, topic):.0f}", flush=True)
        session_id = _session_id(mode, learner.id, topic, seed)
        existing_count = db.query(AnswerRecord).filter(
            AnswerRecord.learner_id == learner.id,
            AnswerRecord.session_id == session_id,
        ).count()
        if existing_count:
            print(f"  [skip] 会话已存在 {session_id}（答题记录={existing_count}）", flush=True)
            continue
        if mode == "adaptive":
            run_adaptive_session(db, learner, topic, session_len, rng, stats, session_id)
        else:
            run_round(
                db,
                learner,
                topic,
                session_len,
                rng,
                stats,
                session_id,
                question_difficulty,
            )
    return stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--learner-ids", default="4,5", help="逗号分隔的学习者ID（默认 4,5：有低难度资源）")
    parser.add_argument("--mode", choices=["adaptive", "round"], default="adaptive", help="adaptive=前端自适应会话（默认），round=批量轮次")
    parser.add_argument("--topics", type=int, default=3, help="每学习者主题数")
    parser.add_argument("--session-len", type=int, default=6, help="adaptive: 每主题会话题数 / round: 每轮题数")
    parser.add_argument(
        "--question-difficulty",
        type=int,
        choices=range(1, 6),
        default=None,
        help="round 模式固定题目难度（不传则使用画像推荐难度）",
    )
    parser.add_argument("--seed", type=int, default=20260825, help="随机种子（可复现）")
    parser.add_argument("--smoke", action="store_true", help="冒烟模式：1 学习者 1 主题 2 题")
    args = parser.parse_args()

    if args.smoke:
        args.learner_ids = args.learner_ids.split(",")[0]
        args.topics, args.session_len = 1, 2

    learner_ids = [int(x) for x in args.learner_ids.split(",") if x.strip()]
    rng = random.Random(args.seed)

    db = SessionLocal()
    try:
        before_total = db.query(AnswerRecord).count()
        before_res = db.query(AnswerRecord).filter(AnswerRecord.next_resource_id.isnot(None)).count()
        print(f"运行前: 答题记录={before_total}, next_resource_id非空={before_res}")
        print(
            f"参数: mode={args.mode} learners={learner_ids} topics={args.topics} "
            f"session_len={args.session_len} question_difficulty={args.question_difficulty} "
            f"seed={args.seed}"
        )

        totals = {"answered": 0, "correct": 0, "with_resource": 0, "intent_match": 0, "failed": 0}
        start = time.time()
        for learner_id in learner_ids:
            learner = db.query(LearnerProfile).filter(LearnerProfile.id == learner_id).first()
            if not learner:
                print(f"[warn] learner={learner_id} 不存在，跳过")
                continue
            stats = run_learner(
                db,
                learner,
                args.mode,
                args.session_len,
                args.topics,
                rng,
                args.seed,
                args.question_difficulty,
            )
            for key in totals:
                totals[key] += stats[key]

        after_total = db.query(AnswerRecord).count()
        after_res = db.query(AnswerRecord).filter(AnswerRecord.next_resource_id.isnot(None)).count()
        dur = time.time() - start
        accuracy = totals["correct"] / totals["answered"] * 100 if totals["answered"] else 0.0
        intent_rate = totals["intent_match"] / totals["answered"] * 100 if totals["answered"] else 0.0
        print(f"\n===== 汇总 =====")
        print(f"答题={totals['answered']} 正确={totals['correct']} 正确率={accuracy:.1f}%")
        print(f"意图命中率={intent_rate:.1f}%（模拟意图与服务端判分一致性）失败={totals['failed']}")
        print(f"答题记录: {before_total} -> {after_total}")
        print(f"next_resource_id非空: {before_res} -> {after_res} (验收要求 >=10)")
        print(f"总耗时 {dur:.0f}s")
        return 0 if totals["answered"] else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
