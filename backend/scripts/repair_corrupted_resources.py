"""Repair legacy resource bodies that were polluted by mock or audit JSON.

Run without arguments to inspect only.  ``--apply`` creates a SQLite backup
before it changes any resource body and never deletes records.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings
from app.database import get_db_context
from app.models import LearningResource
from app.utils.llm import LLMUtil
from app.utils.resource_content import ResourceContentError, normalize_resource_content


def parse_json(value: Any) -> Any:
    result = value
    for _ in range(3):
        if not isinstance(result, str):
            return result
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            return None
    return result


def extract_enveloped_content(value: Any) -> str | None:
    decoded = parse_json(value)
    if not isinstance(decoded, Mapping):
        return None
    content = decoded.get("content")
    return content.strip() if isinstance(content, str) and content.strip() else None


def is_legacy_mock_content(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    decoded = parse_json(value)
    if isinstance(decoded, Mapping):
        meta = decoded.get("_meta")
        if isinstance(meta, Mapping) and str(meta.get("model", "")).strip().lower() == "mock":
            return True
    return any(
        marker in value
        for marker in (
            "LLM unavailable, deterministic fallback",
            '"_meta": {"model": "mock"}',
            '\\"_meta\\": {\\"model\\": \\"mock\\"}',
        )
    )


def render_exercises(title: str, content_json: Any) -> str | None:
    payload = parse_json(content_json)
    if not isinstance(payload, Mapping):
        return None

    groups = (
        ("基础题", payload.get("basic_questions")),
        ("进阶挑战题", payload.get("advanced_questions")),
    )
    lines = [f"# {title}", ""]
    question_count = 0
    for heading, questions in groups:
        if not isinstance(questions, list) or not questions:
            continue
        lines.extend([f"## {heading}", ""])
        for index, question in enumerate(questions, 1):
            if not isinstance(question, Mapping):
                continue
            prompt = str(question.get("question") or "").strip()
            options = question.get("options")
            if not prompt or not isinstance(options, list):
                continue
            lines.extend([f"### 第{index}题：{prompt}", ""])
            for option_index, option in enumerate(options):
                lines.append(f"- {chr(65 + option_index)}. {str(option).strip()}")
            lines.append("")
            question_count += 1
    return "\n".join(lines).strip() if question_count else None


def render_sections(title: str, content_json: Any, key: str) -> str | None:
    payload = parse_json(content_json)
    if not isinstance(payload, Mapping):
        return None
    sections = payload.get(key)
    if not isinstance(sections, list):
        return None
    lines = [f"# {title}", ""]
    section_count = 0
    for section in sections:
        if not isinstance(section, Mapping):
            continue
        heading = str(section.get("title") or "").strip()
        content = str(section.get("content") or "").strip()
        if not heading or not content:
            continue
        lines.extend([f"## {heading}", "", content, ""])
        section_count += 1
    return "\n".join(lines).strip() if section_count else None


def recover_content(resource: LearningResource) -> str | None:
    try:
        return normalize_resource_content(resource.content)
    except ResourceContentError:
        pass

    if not is_legacy_mock_content(resource.content):
        recovered = extract_enveloped_content(resource.content)
        if recovered:
            return recovered
    if resource.resource_type == "exercise":
        return render_exercises(resource.title, resource.content_json)
    if resource.resource_type == "guide":
        return render_sections(resource.title, resource.content_json, "chapters")
    if resource.resource_type == "lecture":
        return render_sections(resource.title, resource.content_json, "sections")
    return None


def regenerate_with_deepseek(resource: LearningResource) -> dict[str, Any]:
    """Create a replacement only when explicitly requested by the operator."""
    from app.agents.llm_generator import LLMGenerator

    diagnosis = {
        "recommended_difficulty": {
            "recommended_difficulty": resource.difficulty_level or 3,
        }
    }
    topic = (resource.knowledge_topic or resource.title or "学习主题").strip()
    if resource.resource_type == "exercise":
        result = LLMGenerator.generate_exercises(diagnosis, [], {}, topic)
    elif resource.resource_type == "lecture":
        result = LLMGenerator.generate_lecture(diagnosis, [], {}, topic)
    else:
        result = LLMGenerator.generate_guide(diagnosis, [], {}, topic)
    result["content"] = normalize_resource_content(result.get("content"))
    return result


def backup_sqlite_database() -> Path | None:
    prefix = "sqlite:///"
    if not settings.DATABASE_URL.startswith(prefix):
        return None
    database_path = Path(settings.DATABASE_URL.removeprefix(prefix))
    if not database_path.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = database_path.with_name(
        f"{database_path.stem}.before-resource-content-repair-{timestamp}{database_path.suffix}"
    )
    shutil.copy2(database_path, backup)
    return backup


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write repaired Markdown after creating a backup")
    parser.add_argument(
        "--regenerate-with-deepseek",
        action="store_true",
        help="replace legacy mock content with a fresh DeepSeek result (requires --apply)",
    )
    args = parser.parse_args()
    if args.regenerate_with_deepseek and not args.apply:
        parser.error("--regenerate-with-deepseek requires --apply")

    with get_db_context() as db:
        resources = (
            db.query(LearningResource)
            .filter(LearningResource.resource_type.in_(("guide", "exercise", "lecture")))
            .order_by(LearningResource.id)
            .all()
        )
        legacy_mock_resources = [resource for resource in resources if is_legacy_mock_content(resource.content)]
        repairs = [(resource, recover_content(resource)) for resource in resources]
        repairable = [(resource, content) for resource, content in repairs if content and content != resource.content]
        unresolved = [resource.id for resource, content in repairs if content is None]
        regenerated: list[int] = []
        regeneration_failures: dict[int, str] = {}

        backup = None
        if args.apply and (repairable or (args.regenerate_with_deepseek and legacy_mock_resources)):
            backup = backup_sqlite_database()
            for resource, content in repairable:
                resource.content = content
                resource.word_count = len(content)
                if resource in legacy_mock_resources:
                    resource.generation_method = "deterministic_fallback"
                    resource.is_validated = False
                    resource.validation_passed = False
                    resource.status = "failed"
                    resource.validation_notes = "legacy mock payload repaired; regenerate with DeepSeek"
                else:
                    resource.generation_method = resource.generation_method or "deterministic_fallback"
            if args.regenerate_with_deepseek:
                for resource in legacy_mock_resources:
                    try:
                        replacement = regenerate_with_deepseek(resource)
                        resource.content = replacement["content"]
                        resource.word_count = len(resource.content)
                        resource.title = replacement.get("resource_title", resource.title)
                        resource.difficulty_level = replacement.get(
                            "difficulty_level", resource.difficulty_level
                        )
                        resource.generation_method = "deepseek"
                        resource.validation_notes = "历史 mock 正文已由 DeepSeek 重新生成，等待正常审核。"
                        regenerated.append(resource.id)
                    except Exception as exc:  # Keep the original row if regeneration fails.
                        regeneration_failures[resource.id] = str(exc)[:200]

        print(
            {
                "mode": "apply" if args.apply else "dry-run",
                "scanned": len(resources),
                "repairable_resource_ids": [resource.id for resource, _ in repairable],
                "legacy_mock_resource_ids": [resource.id for resource in legacy_mock_resources],
                "regenerated_resource_ids": regenerated,
                "regeneration_failures": regeneration_failures,
                "unresolved_resource_ids": unresolved,
                "backup": str(backup) if backup else None,
            }
        )


if __name__ == "__main__":
    main()
