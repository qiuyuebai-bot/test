"""Task 1 归因分析（只读）：答题正确率 23.53% 与资源匹配效果 16.67% 的根因定位。

用法:
  cd backend
  python -m scripts.analyze_answer_records [--db ../data/app.db]

产出:
  - 控制台摘要（四问四答）
  - docs/evidence/answer-attribution.json（供评分材料引用）
"""
import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = PROJECT_ROOT / "data" / "app.db"

ATTRIBUTION_PATH = PROJECT_ROOT / "docs" / "evidence" / "answer-attribution.json"


def fetch(db_path: Path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    records = cur.execute(
        """
        SELECT ar.id, ar.learner_id, ar.question_difficulty, ar.question_topic,
               ar.result, ar.agent_decision, ar.next_question_difficulty,
               ar.next_resource_id, ar.decision_confidence, ar.created_at
        FROM answer_records ar
        ORDER BY ar.learner_id, ar.id
        """
    ).fetchall()

    profiles = {
        r["id"]: dict(r)
        for r in cur.execute(
            """
            SELECT id, display_name, real_name, preferred_difficulty,
                   theoretical_foundation, programming_ability, algorithm_design,
                   system_architecture, data_analysis, engineering_practice,
                   total_questions_answered, total_correct_rate
            FROM learner_profiles
            """
        ).fetchall()
    }

    resource_difficulty = {
        r["id"]: r["difficulty_level"]
        for r in cur.execute(
            "SELECT id, difficulty_level FROM learning_resources"
        ).fetchall()
    }

    conn.close()
    return records, profiles, resource_difficulty


def analyze(records, profiles, resource_difficulty):
    total = len(records)
    correct = sum(1 for r in records if r["result"] == "correct")

    # 问题1: 难度分布 vs 画像 preferred_difficulty / 能力分
    diff_dist = Counter(r["question_difficulty"] for r in records)
    wrong_diff_dist = Counter(
        r["question_difficulty"] for r in records if r["result"] != "correct"
    )
    over_profile = 0
    per_learner = {}
    for r in records:
        p = profiles.get(r["learner_id"])
        if not p:
            continue
        ability = (
            p["theoretical_foundation"] + p["programming_ability"]
            + p["algorithm_design"] + p["system_architecture"]
            + p["data_analysis"] + p["engineering_practice"]
        ) / 6
        entry = per_learner.setdefault(
            p["id"],
            {
                "display_name": p["display_name"] or p["real_name"],
                "preferred_difficulty": p["preferred_difficulty"],
                "avg_ability": round(ability, 1),
                "n": 0, "correct": 0,
                "difficulties": [], "mismatch": 0,
            },
        )
        entry["n"] += 1
        entry["correct"] += 1 if r["result"] == "correct" else 0
        entry["difficulties"].append(r["question_difficulty"])
        # 错题难度超出画像偏好2级以上记为错配
        if r["result"] != "correct" and r["question_difficulty"] >= (p["preferred_difficulty"] or 3) + 2:
            entry["mismatch"] += 1
            over_profile += 1
    for e in per_learner.values():
        e["difficulty_dist"] = dict(Counter(e.pop("difficulties")))
        e["accuracy"] = round(100 * e["correct"] / e["n"], 1) if e["n"] else 0.0

    # 问题2: agent_decision 分布 + 答错后难度是否降级
    decision_dist = Counter(r["agent_decision"] for r in records)
    wrong_records = [r for r in records if r["result"] != "correct"]
    downgrade_after_wrong = sum(
        1 for r in wrong_records
        if r["next_question_difficulty"] is not None
        and r["next_question_difficulty"] < r["question_difficulty"]
    )
    hold_after_wrong = sum(
        1 for r in wrong_records
        if r["next_question_difficulty"] == r["question_difficulty"]
    )
    upgrade_after_wrong = sum(
        1 for r in wrong_records
        if r["next_question_difficulty"] is not None
        and r["next_question_difficulty"] > r["question_difficulty"]
    )

    # 问题3: next_resource_id 为空的原因统计（answer_record 与 decision_log 中 suggested_resources）
    linked = [r for r in records if r["next_resource_id"] is not None]
    linked_correct = sum(1 for r in linked if r["result"] == "correct")
    linked_diff_gap = Counter()
    for r in linked:
        rd = resource_difficulty.get(r["next_resource_id"])
        p = profiles.get(r["learner_id"])
        if rd is not None and p and p["preferred_difficulty"]:
            linked_diff_gap[rd - p["preferred_difficulty"]] += 1

    # 问题4: 答题会话内难度序列是否体现自适应（同 learner 连续记录）
    seq_up = seq_down = seq_flat = 0
    by_learner_seq = {}
    for r in records:
        by_learner_seq.setdefault(r["learner_id"], []).append(r)
    for seq in by_learner_seq.values():
        for prev, nxt in zip(seq, seq[1:]):
            if nxt["question_difficulty"] is None or prev["question_difficulty"] is None:
                continue
            if nxt["question_difficulty"] > prev["question_difficulty"]:
                seq_up += 1
            elif nxt["question_difficulty"] < prev["question_difficulty"]:
                seq_down += 1
            else:
                seq_flat += 1

    return {
        "total_answer_records": total,
        "correct_count": correct,
        "answer_accuracy": round(100 * correct / total, 2) if total else 0.0,
        "q1_difficulty_vs_profile": {
            "difficulty_distribution": {str(k): v for k, v in sorted(diff_dist.items(), key=lambda x: (x[0] is None, x[0]))},
            "wrong_answer_difficulty_distribution": {str(k): v for k, v in sorted(wrong_diff_dist.items(), key=lambda x: (x[0] is None, x[0]))},
            "wrong_answers_exceeding_profile_by_2_levels": over_profile,
            "per_learner": per_learner,
        },
        "q2_decision_loop": {
            "agent_decision_distribution": dict(decision_dist),
            "after_wrong_answer": {
                "difficulty_downgraded": downgrade_after_wrong,
                "difficulty_held": hold_after_wrong,
                "difficulty_upgraded": upgrade_after_wrong,
                "wrong_total": len(wrong_records),
            },
        },
        "q3_resource_linkage": {
            "records_with_next_resource": len(linked),
            "linked_correct": linked_correct,
            "linked_resource_minus_preferred_difficulty": {str(k): v for k, v in sorted(linked_diff_gap.items(), key=lambda x: (x[0] is None, x[0]))},
        },
        "q4_intra_session_adaptivity": {
            "consecutive_pairs_difficulty_up": seq_up,
            "consecutive_pairs_difficulty_down": seq_down,
            "consecutive_pairs_difficulty_flat": seq_flat,
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite 数据库路径")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"数据库不存在: {db_path}")
        sys.exit(1)

    records, profiles, resource_difficulty = fetch(db_path)
    result = analyze(records, profiles, resource_difficulty)
    result["db_path"] = str(db_path)
    result["analyzed_at"] = datetime.now(timezone.utc).isoformat()

    ATTRIBUTION_PATH.parent.mkdir(parents=True, exist_ok=True)
    ATTRIBUTION_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"数据库: {db_path}")
    print(f"答题总数 {result['total_answer_records']}，正确 {result['correct_count']}"
          f"（正确率 {result['answer_accuracy']}%）")
    print(f"Q1 难度分布: {result['q1_difficulty_vs_profile']['difficulty_distribution']}")
    print(f"Q1 错题难度分布: {result['q1_difficulty_vs_profile']['wrong_answer_difficulty_distribution']}")
    print(f"Q1 超出画像偏好2级的错题: {result['q1_difficulty_vs_profile']['wrong_answers_exceeding_profile_by_2_levels']} 条")
    print(f"Q2 决策分布: {result['q2_decision_loop']['agent_decision_distribution']}")
    print(f"Q2 答错后难度变化: {result['q2_decision_loop']['after_wrong_answer']}")
    print(f"Q3 有资源链接的答题: {result['q3_resource_linkage']['records_with_next_resource']}"
          f"，其中答对 {result['q3_resource_linkage']['linked_correct']}")
    print(f"Q4 相邻答题难度 up/down/flat: {result['q4_intra_session_adaptivity']}")
    print(f"归因结果已写入: {ATTRIBUTION_PATH}")


if __name__ == "__main__":
    main()
