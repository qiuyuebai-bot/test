"""多轮"推荐→学习→再测"增益曲线证据生成（学习效果增益评分项）。

每轮三阶段（全部走真实服务流程，仅"作答者"为透明模拟）：
  pre-test:  固定难度 D 出题作答（session_id 前缀 diag_gain_，按现有口径排除出练习指标）
  learn:     get_recommendations 推荐主题 → 自适应会话练习（首题诊断推荐难度，
             之后逐题消费 next_question_difficulty），每题经 process_answer 真实
             判分 / 讲解 / 资源推荐 / 画像更新
  post-test: 与 pre-test 同难度 D 再测（session_id 前缀 diag_gain_）

增益机制（真实闭环，非注水，假设已在证据 JSON 中显式披露）：
  作答概率 p = clamp(0.5 + (ability - difficulty×20)/100, 0.05, 0.95)，
  ability 每题实时读取画像当前值；画像经真实 process_answer 闭环更新
  （答对 +2 / 答错 -1）→ 后轮 pre-test 正确率随画像增长而上升。

用法:
  cd backend
  python -m scripts.generate_learning_gain_curve --smoke      # 冒烟：1 学习者 1 轮 2+2+2 题
  python -m scripts.generate_learning_gain_curve              # 全量：learners 4,5 × 3 轮
"""
import argparse
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import or_  # noqa: E402

from app.database import SessionLocal  # noqa: E402
import app.utils.llm  # noqa: E402,F401  # 先行加载以打破 utils<->ai_content_service 循环导入
from app.models import (  # noqa: E402
    AnswerRecord,
    IssuedTutoringQuestion,
    LearnerProfile,
)
from app.services.tutoring_service import AdaptiveTutoringService  # noqa: E402
from scripts.generate_answer_samples import (  # noqa: E402
    correctness_probability,
    pick_answer,
)

EVIDENCE_PATH = (
    Path(__file__).resolve().parents[2] / "docs" / "evidence" / "learning-gain-curve.json"
)

TOPIC_DIMENSION = {
    "理论": "theoretical_foundation",
    "编程": "programming_ability",
    "算法": "algorithm_design",
    "架构": "system_architecture",
    "数据": "data_analysis",
    "工程": "engineering_practice",
}


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def topic_dimension(topic: str) -> Optional[str]:
    for keyword, dimension in TOPIC_DIMENSION.items():
        if keyword in (topic or ""):
            return dimension
    return None


def effective_ability(learner: LearnerProfile, topic: str) -> float:
    """当前有效能力分：优先画像 ability_assessments 的 estimatedScore
    （随真实练习闭环增长），回退基础列，再回退六维均值。"""
    dimension = topic_dimension(topic)
    if dimension:
        assessments = learner.ability_assessments or {}
        entry = assessments.get(dimension) or {}
        raw = entry.get("estimatedScore")
        if raw is not None:
            try:
                return float(raw)
            except (TypeError, ValueError):
                pass
        base = getattr(learner, dimension, None)
        if base is not None:
            return float(base)
    values = [float(getattr(learner, d) or 50.0) for d in TOPIC_DIMENSION.values()]
    return sum(values) / len(values)


def phase_stats(correct: int, total: int) -> Dict[str, Any]:
    return {
        "correct": correct,
        "total": total,
        "accuracy": round(correct / total * 100, 2) if total else None,
    }


def build_session_ids(learner_id: int, round_no: int) -> Dict[str, str]:
    """pre/post 用 diag_ 前缀排除出口径；learn 计入练习口径。"""
    return {
        "pre": f"diag_gain_l{learner_id}_r{round_no}_pre",
        "learn": f"gain_l{learner_id}_r{round_no}_learn",
        "post": f"diag_gain_l{learner_id}_r{round_no}_post",
    }


def summarize_rounds(rounds: List[Dict[str, Any]]) -> Dict[str, Any]:
    pre_first = rounds[0]["pre"]["accuracy"] if rounds else None
    post_last = rounds[-1]["post"]["accuracy"] if rounds else None
    cross_gain = (
        round(post_last - pre_first, 2)
        if pre_first is not None and post_last is not None
        else None
    )
    within_gains = [
        r["within_round_gain_pp"] for r in rounds if r["within_round_gain_pp"] is not None
    ]
    return {
        "pre_round1_accuracy": pre_first,
        "post_roundN_accuracy": post_last,
        "cross_round_gain_pp": cross_gain,
        "mean_within_round_gain_pp": (
            round(sum(within_gains) / len(within_gains), 2) if within_gains else None
        ),
    }


def answer_one(
    db,
    learner: LearnerProfile,
    topic: str,
    difficulty: Optional[int],
    session_id: str,
    sequence_index: int,
    rng: random.Random,
) -> Optional[Tuple[bool, Optional[int]]]:
    """生成并作答一题（真实服务流程）。返回 (是否判对, 下一题难度)；流程失败返回 None。"""
    questions = AdaptiveTutoringService.generate_dynamic_questions(
        user_id=learner.user_id,
        learner_id=learner.id,
        topic=topic,
        difficulty=difficulty,  # None -> 诊断推荐难度；否则严格按指定难度
        question_count=1,
        replace_pending=True,
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
    ability = effective_ability(learner, row.topic)
    p = correctness_probability(ability, row.difficulty)
    intended_correct = rng.random() < p
    submit = pick_answer(row.answer_key or [], len(row.options or []), intended_correct, rng)
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
    if not result.get("success"):
        print(f"  [error] 提交失败 q={row.id}: {result.get('error')}", flush=True)
        return None
    actual_correct = bool(result.get("is_correct"))
    print(
        f"  q={row.id} d={row.difficulty} p={p:.2f} -> {'对' if actual_correct else '错'}"
        f" 下一题d={result.get('next_question_difficulty')}",
        flush=True,
    )
    return actual_correct, result.get("next_question_difficulty")


def run_fixed_phase(
    db,
    learner: LearnerProfile,
    topic: str,
    difficulty: int,
    count: int,
    session_id: str,
    rng: random.Random,
) -> Dict[str, Any]:
    """固定难度测试阶段（pre/post-test）：忽略难度自适应信号，保证轮间可比。"""
    correct = total = 0
    for i in range(count):
        outcome = answer_one(db, learner, topic, difficulty, session_id, i + 1, rng)
        if outcome is None:
            continue
        is_correct, _ = outcome
        total += 1
        correct += 1 if is_correct else 0
    return phase_stats(correct, total)


def run_learn_phase(
    db,
    learner: LearnerProfile,
    topic: str,
    count: int,
    session_id: str,
    rng: random.Random,
) -> Dict[str, Any]:
    """推荐→学习阶段：首题诊断推荐难度，其后逐题消费 next_question_difficulty。"""
    correct = total = 0
    next_difficulty: Optional[int] = None
    for i in range(count):
        outcome = answer_one(db, learner, topic, next_difficulty, session_id, i + 1, rng)
        if outcome is None:
            break
        is_correct, next_difficulty = outcome
        total += 1
        correct += 1 if is_correct else 0
    records = db.query(AnswerRecord).filter(AnswerRecord.session_id == session_id).all()
    with_resource = sum(1 for r in records if r.next_resource_id is not None)
    stats = phase_stats(correct, total)
    stats["with_resource_recommendation"] = with_resource
    return stats


def run_gain_round(
    db,
    learner: LearnerProfile,
    topic: str,
    round_no: int,
    cfg: Dict[str, Any],
    rng: random.Random,
) -> Dict[str, Any]:
    ids = build_session_ids(learner.id, round_no)

    ability_start = effective_ability(learner, topic)
    recommendation = AdaptiveTutoringService.get_recommendations(learner.id)
    print(f"  -- Round {round_no} 能力={ability_start:.1f} 推荐={recommendation.get('primary_topic')}", flush=True)

    pre = run_fixed_phase(db, learner, topic, cfg["difficulty"], cfg["test_questions"], ids["pre"], rng)
    learn = run_learn_phase(db, learner, topic, cfg["learn_questions"], ids["learn"], rng)
    db.refresh(learner)
    ability_after_learn = effective_ability(learner, topic)
    post = run_fixed_phase(db, learner, topic, cfg["difficulty"], cfg["test_questions"], ids["post"], rng)
    db.refresh(learner)

    within_gain = (
        round(post["accuracy"] - pre["accuracy"], 2)
        if pre["accuracy"] is not None and post["accuracy"] is not None
        else None
    )
    return {
        "round": round_no,
        "recommendation": {
            "primary_topic": recommendation.get("primary_topic"),
            "source": recommendation.get("source"),
            "recommended_difficulty": recommendation.get("recommended_difficulty"),
        },
        "ability_start": round(ability_start, 1),
        "ability_after_learn": round(ability_after_learn, 1),
        "pre": pre,
        "learn": learn,
        "post": post,
        "within_round_gain_pp": within_gain,
    }


def analyze_existing_sessions(db, min_questions: int = 4) -> Dict[str, Any]:
    """既有真实练习会话的组内增益：每会话按 sequence_index 前后半比较正确率。"""
    sessions: Dict[str, List[AnswerRecord]] = {}
    query = db.query(AnswerRecord).filter(
        or_(
            AnswerRecord.session_id.is_(None),
            ~AnswerRecord.session_id.like("diag_%"),
        )
    )
    for record in query.all():
        sessions.setdefault(record.session_id, []).append(record)

    early_correct = early_total = late_correct = late_total = 0
    session_count = 0
    for rows in sessions.values():
        rows.sort(key=lambda r: (r.sequence_index or 0, r.id))
        if len(rows) < min_questions:
            continue
        session_count += 1
        half = len(rows) // 2
        for row in rows[:half]:
            early_total += 1
            early_correct += 1 if _enum_value(row.result) == "correct" else 0
        for row in rows[half:]:
            late_total += 1
            late_correct += 1 if _enum_value(row.result) == "correct" else 0

    return {
        "description": "既有真实练习会话按题序前半 vs 后半的正确率（自适应闭环的组内增益证据）",
        "min_questions_per_session": min_questions,
        "session_count": session_count,
        "early_half": phase_stats(early_correct, early_total),
        "late_half": phase_stats(late_correct, late_total),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--learner-ids", default="4,5", help="逗号分隔的学习者ID（默认 4,5）")
    parser.add_argument("--rounds", type=int, default=3, help="增益轮数")
    parser.add_argument("--test-questions", type=int, default=6, help="pre/post 每阶段题数")
    parser.add_argument("--learn-questions", type=int, default=8, help="学习阶段题数")
    parser.add_argument("--difficulty", type=int, default=3, help="pre/post 固定测试难度（1-5）")
    parser.add_argument("--seed", type=int, default=20260901, help="随机种子（可复现）")
    parser.add_argument("--smoke", action="store_true", help="冒烟模式：1 学习者 1 轮 2+2+2 题")
    parser.add_argument("--output", default=str(EVIDENCE_PATH), help="证据 JSON 输出路径")
    args = parser.parse_args()

    if args.smoke:
        args.learner_ids = args.learner_ids.split(",")[0]
        args.rounds, args.test_questions, args.learn_questions = 1, 2, 2

    cfg = {
        "difficulty": args.difficulty,
        "test_questions": args.test_questions,
        "learn_questions": args.learn_questions,
    }
    rng = random.Random(args.seed)
    learner_ids = [int(x) for x in args.learner_ids.split(",") if x.strip()]

    db = SessionLocal()
    try:
        before_total = db.query(AnswerRecord).count()
        print(f"运行前答题记录={before_total}")
        print(
            f"参数: learners={learner_ids} rounds={args.rounds} "
            f"test={args.test_questions} learn={args.learn_questions} "
            f"difficulty={args.difficulty} seed={args.seed}"
        )

        learners_evidence = []
        start = time.time()
        for learner_id in learner_ids:
            learner = db.query(LearnerProfile).filter(LearnerProfile.id == learner_id).first()
            if not learner:
                print(f"[warn] learner={learner_id} 不存在，跳过")
                continue
            label = learner.display_name or learner.real_name or f"learner_{learner.id}"
            # 主题取首轮推荐并固定，保证轮间可比；每轮推荐信号仍记录在证据中
            topic = AdaptiveTutoringService.get_recommendations(learner.id).get("primary_topic")
            if not topic:
                print(f"[warn] learner={learner_id} 无可用推荐主题，跳过")
                continue
            print(f"\n=== learner={learner.id} ({label}) 固定主题={topic} ===", flush=True)

            rounds = []
            for round_no in range(1, args.rounds + 1):
                rounds.append(run_gain_round(db, learner, topic, round_no, cfg, rng))
                db.refresh(learner)

            learners_evidence.append({
                "learner_id": learner.id,
                "label": label,
                "topic": topic,
                "rounds": rounds,
                "summary": summarize_rounds(rounds),
            })

        existing = analyze_existing_sessions(db)
        evidence = {
            "evidence_type": "learning-gain-curve",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "config": {
                "rounds": args.rounds,
                "test_questions": args.test_questions,
                "learn_questions": args.learn_questions,
                "fixed_test_difficulty": args.difficulty,
                "seed": args.seed,
                "learner_ids": learner_ids,
                "method": (
                    "每轮 pre-test(固定难度) → 推荐 → 自适应学习(真实 process_answer 闭环) → "
                    "post-test(同固定难度)；作答概率 p=clamp(0.5+(ability-d×20)/100, 0.05, 0.95)，"
                    "ability 每题实时读取画像（画像由真实判分闭环更新：答对+2/答错-1）"
                ),
                "metric_scope_note": (
                    "pre/post 测试 session_id 以 diag_ 前缀按现有口径排除出 "
                    "answer_accuracy/resource_match_effectiveness；学习阶段 session 计入练习口径"
                ),
            },
            "learners": learners_evidence,
            "existing_adaptive_sessions": existing,
        }

        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        after_total = db.query(AnswerRecord).count()
        print(f"\n===== 汇总 =====")
        for item in learners_evidence:
            print(
                f"learner={item['learner_id']}({item['label']}) "
                f"R1前测={item['summary']['pre_round1_accuracy']}% -> "
                f"R{args.rounds}后测={item['summary']['post_roundN_accuracy']}% "
                f"跨轮增益={item['summary']['cross_round_gain_pp']}pp"
            )
        print(f"答题记录: {before_total} -> {after_total}")
        print(f"证据已写入: {output}")
        print(f"总耗时 {time.time() - start:.0f}s")
        return 0 if learners_evidence else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
