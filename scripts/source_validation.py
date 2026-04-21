#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

SKILL_CATEGORIES = {
    "skill",
    "tool",
    "language",
    "knowledge",
    "project",
    "interest",
    "soft_skill",
    "constraint",
}

RELATION_FIELDS = ("supports", "requires", "prefers", "evidences", "inhibits")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _require_string(value: Any, field: str, context: str) -> str:
    _require(isinstance(value, str) and value.strip(), f"{context}.{field} must be a non-empty string")
    return value.strip()


def _require_string_list(value: Any, field: str, context: str) -> list[str]:
    _require(isinstance(value, list), f"{context}.{field} must be a list")
    normalized: list[str] = []
    for index, item in enumerate(value):
        normalized.append(_require_string(item, f"{field}[{index}]", context))
    return normalized


def _validate_skill_sources(skills: Any) -> tuple[set[str], int]:
    _require(isinstance(skills, dict), "skills.json must be an object")
    unknown_categories = sorted(set(skills) - SKILL_CATEGORIES)
    _require(not unknown_categories, f"skills.json contains unsupported categories: {unknown_categories}")
    missing_categories = sorted(SKILL_CATEGORIES - set(skills))
    _require(not missing_categories, f"skills.json is missing categories: {missing_categories}")

    node_ids: set[str] = set()
    item_count = 0
    for category, items in skills.items():
        _require(isinstance(items, list), f"skills.json.{category} must be a list")
        for index, item in enumerate(items):
            context = f"skills.json.{category}[{index}]"
            _require(isinstance(item, dict), f"{context} must be an object")
            node_id = _require_string(item.get("id"), "id", context)
            _require(node_id not in node_ids, f"duplicate node id detected in skills.json: {node_id}")
            node_ids.add(node_id)
            _require_string(item.get("name"), "name", context)
            aliases = item.get("aliases", [])
            _require(isinstance(aliases, list), f"{context}.aliases must be a list")
            for alias_index, alias in enumerate(aliases):
                _require_string(alias, f"aliases[{alias_index}]", context)
            description = item.get("description")
            if description is not None:
                _require_string(description, "description", context)
            item_count += 1
    return node_ids, item_count


def _collect_template_ids(templates: Any) -> tuple[set[str], int]:
    _require(isinstance(templates, dict), "capability_templates.json must be an object")
    expected_groups = {"abilities", "composites", "directions"}
    missing_groups = sorted(expected_groups - set(templates))
    _require(not missing_groups, f"capability_templates.json is missing groups: {missing_groups}")

    node_ids: set[str] = set()
    item_count = 0
    for group in ("abilities", "composites", "directions"):
        items = templates.get(group, [])
        _require(isinstance(items, list), f"capability_templates.json.{group} must be a list")
        for index, item in enumerate(items):
            context = f"capability_templates.json.{group}[{index}]"
            _require(isinstance(item, dict), f"{context} must be an object")
            node_id = _require_string(item.get("id"), "id", context)
            _require(node_id not in node_ids, f"duplicate template id detected: {node_id}")
            node_ids.add(node_id)
            _require_string(item.get("name"), "name", context)
            for field in RELATION_FIELDS:
                values = item.get(field, [])
                _require(isinstance(values, list), f"{context}.{field} must be a list")
                for value_index, value in enumerate(values):
                    _require_string(value, f"{field}[{value_index}]", context)
            item_count += 1
    return node_ids, item_count


def _collect_role_ids(roles: Any) -> tuple[set[str], int]:
    _require(isinstance(roles, dict), "roles.json must be an object")
    _require(isinstance(roles.get("standalone_roles", []), list), "roles.json.standalone_roles must be a list")
    _require(isinstance(roles.get("specializations", []), list), "roles.json.specializations must be a list")

    node_ids: set[str] = set()
    item_count = 0

    for index, item in enumerate(roles.get("standalone_roles", [])):
        context = f"roles.json.standalone_roles[{index}]"
        _require(isinstance(item, dict), f"{context} must be an object")
        role_id = _require_string(item.get("id"), "id", context)
        _require(role_id not in node_ids, f"duplicate standalone role id detected: {role_id}")
        node_ids.add(role_id)
        _require_string(item.get("name"), "name", context)
        _require_string(item.get("direction_id"), "direction_id", context)
        _require_string(item.get("capability_id"), "capability_id", context)
        for field in RELATION_FIELDS:
            values = item.get(field, [])
            _require(isinstance(values, list), f"{context}.{field} must be a list")
            for value_index, value in enumerate(values):
                _require_string(value, f"{field}[{value_index}]", context)
        item_count += 1

    for index, item in enumerate(roles.get("specializations", [])):
        context = f"roles.json.specializations[{index}]"
        _require(isinstance(item, dict), f"{context} must be an object")
        for field in (
            "stack_ability_id",
            "stack_ability_name",
            "base_capability_id",
            "capability_id",
            "capability_name",
            "direction_id",
            "role_id",
            "role_name",
        ):
            _require_string(item.get(field), field, context)

        for field in ("stack_ability_id", "capability_id", "role_id"):
            value = str(item[field]).strip()
            _require(value not in node_ids, f"duplicate specialization id detected: {value}")
            node_ids.add(value)

        for field in (
            "stack_supports",
            "stack_requires",
            "stack_prefers",
            "stack_evidences",
            "stack_inhibits",
            "capability_supports",
            "capability_requires",
            "capability_prefers",
            "capability_evidences",
            "capability_inhibits",
            "role_supports",
            "role_requires",
            "role_prefers",
            "role_evidences",
            "role_inhibits",
        ):
            values = item.get(field, [])
            _require(isinstance(values, list), f"{context}.{field} must be a list")
            for value_index, value in enumerate(values):
                _require_string(value, f"{field}[{value_index}]", context)
        item_count += 1

    return node_ids, item_count


def _validate_reference_lists(payload: dict[str, Any], known_ids: set[str], context: str) -> None:
    for field in RELATION_FIELDS:
        for value in payload.get(field, []):
            _require(value in known_ids, f"{context}.{field} references unknown node id: {value}")


def _validate_relations(relations: Any) -> None:
    _require(isinstance(relations, dict), "relations.json must be an object")
    _require(isinstance(relations.get("layer_defaults"), dict), "relations.json.layer_defaults must be an object")
    _require(
        isinstance(relations.get("specialization_defaults"), dict),
        "relations.json.specialization_defaults must be an object",
    )
    preference_patterns = relations.get("preference_patterns", {})
    _require(isinstance(preference_patterns, dict), "relations.json.preference_patterns must be an object")
    for key, values in preference_patterns.items():
        _require_string_list(values, key, "relations.json.preference_patterns")


def validate_sources(base_dir: Path | None = None) -> dict[str, int]:
    base_dir = base_dir or ROOT
    sources_dir = base_dir / "data" / "sources"

    skills = _load_json(sources_dir / "skills.json")
    templates = _load_json(sources_dir / "capability_templates.json")
    roles = _load_json(sources_dir / "roles.json")
    relations = _load_json(sources_dir / "relations.json")

    skill_ids, skill_count = _validate_skill_sources(skills)
    template_ids, template_count = _collect_template_ids(templates)
    role_ids, role_count = _collect_role_ids(roles)
    _validate_relations(relations)

    known_ids = set(skill_ids) | set(template_ids) | set(role_ids)

    for group in ("abilities", "composites", "directions"):
        for index, item in enumerate(templates.get(group, [])):
            _validate_reference_lists(item, known_ids, f"capability_templates.json.{group}[{index}]")

    for index, item in enumerate(roles.get("standalone_roles", [])):
        _validate_reference_lists(item, known_ids, f"roles.json.standalone_roles[{index}]")
        _require(
            item["direction_id"] in known_ids,
            f"roles.json.standalone_roles[{index}].direction_id references unknown node id: {item['direction_id']}",
        )
        _require(
            item["capability_id"] in known_ids,
            f"roles.json.standalone_roles[{index}].capability_id references unknown node id: {item['capability_id']}",
        )

    for index, item in enumerate(roles.get("specializations", [])):
        for field in ("base_capability_id", "direction_id"):
            _require(
                item[field] in known_ids,
                f"roles.json.specializations[{index}].{field} references unknown node id: {item[field]}",
            )
        for field in (
            "stack_supports",
            "stack_requires",
            "stack_prefers",
            "stack_evidences",
            "stack_inhibits",
            "capability_supports",
            "capability_requires",
            "capability_prefers",
            "capability_evidences",
            "capability_inhibits",
            "role_supports",
            "role_requires",
            "role_prefers",
            "role_evidences",
            "role_inhibits",
        ):
            for value in item.get(field, []):
                _require(
                    value in known_ids,
                    f"roles.json.specializations[{index}].{field} references unknown node id: {value}",
                )

    return {
        "skill_items": skill_count,
        "template_items": template_count,
        "role_items": role_count,
        "known_node_ids": len(known_ids),
    }


def main() -> None:
    summary = validate_sources()
    print(
        "validated source bundle "
        f"({summary['skill_items']} evidence items, {summary['template_items']} templates, "
        f"{summary['role_items']} roles/specializations, {summary['known_node_ids']} node ids)"
    )


if __name__ == "__main__":
    main()
