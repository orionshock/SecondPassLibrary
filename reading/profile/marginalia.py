from __future__ import annotations

from typing import Any

from ..models import Annotation, SELECTOR_KIND_EPUB_CFI


def _iso(value) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def profile_annotation_from_model(annotation: Annotation) -> dict[str, Any]:
    return {
        "motivation": profile_annotation_motivations(annotation),
        "target": {"selector": profile_annotation_selector(annotation)},
        "body": profile_annotation_body(annotation),
        "is_deleted": bool(annotation.is_deleted),
        "created_at": _iso(annotation.created_at),
        "updated_at": _iso(annotation.updated_at),
    }


def profile_annotation_motivations(annotation: Annotation) -> list[str]:
    if annotation.anchor_kind == Annotation.ANCHOR_KIND_BOOKMARK:
        return [Annotation.MOTIVATION_BOOKMARKING]
    motivations = [Annotation.MOTIVATION_HIGHLIGHTING]
    if (annotation.comment_text or "").strip():
        motivations.append(Annotation.MOTIVATION_COMMENTING)
    return motivations


def profile_annotation_selector(annotation: Annotation) -> dict[str, Any] | list[dict[str, Any]]:
    fragment: dict[str, Any] = {
        "type": "FragmentSelector",
        "value": annotation.selector_value,
    }
    if annotation.selector_kind != SELECTOR_KIND_EPUB_CFI:
        fragment["type"] = "UnknownSelector"

    if annotation.highlight_text and (annotation.quote_prefix or annotation.quote_suffix):
        quote: dict[str, Any] = {
            "type": "TextQuoteSelector",
            "exact": annotation.highlight_text,
        }
        if annotation.quote_prefix:
            quote["prefix"] = annotation.quote_prefix
        if annotation.quote_suffix:
            quote["suffix"] = annotation.quote_suffix
        return [fragment, quote]
    return fragment


def profile_annotation_body(annotation: Annotation) -> list[dict[str, Any]]:
    bodies: list[dict[str, Any]] = []
    if annotation.highlight_text or annotation.highlight_color:
        bodies.append(
            {
                "type": "TextualBody",
                "purpose": "describing",
                "value": annotation.highlight_text or "",
                "color": annotation.highlight_color or "yellow",
            }
        )
    if annotation.comment_text:
        bodies.append(
            {
                "type": "TextualBody",
                "purpose": "commenting",
                "value": annotation.comment_text,
            }
        )
    return bodies


def compact_annotation_from_profile(profile_annotation: dict[str, Any]) -> dict[str, str] | None:
    motivations = set(profile_annotation.get("motivation") or [])
    selector = profile_selectors(profile_annotation.get("target") or {})
    fragment = next((item for item in selector if item.get("type") == "FragmentSelector"), {})
    quote = next((item for item in selector if item.get("type") == "TextQuoteSelector"), {})
    selector_value = fragment.get("value") or ""
    if not selector_value:
        return None

    describing = ""
    color = ""
    comment = ""
    for body in profile_annotation.get("body") or []:
        if body.get("purpose") == "describing" and not describing:
            describing = body.get("value") or ""
            color = body.get("color") or ""
        elif body.get("purpose") == "commenting" and not comment:
            comment = body.get("value") or ""

    if Annotation.MOTIVATION_HIGHLIGHTING in motivations:
        highlight_text = describing or quote.get("exact") or ""
        if not highlight_text:
            return None
        return {
            "motivation": Annotation.MOTIVATION_HIGHLIGHTING,
            "anchor_kind": Annotation.ANCHOR_KIND_HIGHLIGHT,
            "selector_value": selector_value,
            "highlight_text": highlight_text,
            "quote_prefix": quote.get("prefix") or "",
            "quote_suffix": quote.get("suffix") or "",
            "highlight_color": color or "yellow",
            "comment_text": comment,
        }
    if Annotation.MOTIVATION_BOOKMARKING in motivations:
        return {
            "motivation": Annotation.MOTIVATION_BOOKMARKING,
            "anchor_kind": Annotation.ANCHOR_KIND_BOOKMARK,
            "selector_value": selector_value,
            "highlight_text": "",
            "quote_prefix": "",
            "quote_suffix": "",
            "highlight_color": "",
            "comment_text": "",
        }
    return None


def profile_selectors(target: dict[str, Any]) -> list[dict[str, Any]]:
    selector = target.get("selector")
    if isinstance(selector, list):
        return [item for item in selector if isinstance(item, dict)]
    if isinstance(selector, dict):
        return [selector]
    return []


def profile_annotation_kind(profile_annotation: dict[str, Any]) -> str:
    motivations = set(profile_annotation.get("motivation") or [])
    if (
        Annotation.MOTIVATION_BOOKMARKING in motivations
        and Annotation.MOTIVATION_HIGHLIGHTING not in motivations
    ):
        return "bookmark"
    if Annotation.MOTIVATION_HIGHLIGHTING in motivations:
        if profile_annotation_has_comment(profile_annotation):
            return "commented_highlight"
        return "highlight"
    return "annotation"


def profile_annotation_has_comment(profile_annotation: dict[str, Any]) -> bool:
    motivations = set(profile_annotation.get("motivation") or [])
    if Annotation.MOTIVATION_COMMENTING in motivations:
        return True
    return any(
        body.get("purpose") == "commenting"
        for body in profile_annotation.get("body") or []
        if isinstance(body, dict)
    )


def count_profile_annotations(sessions: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "annotation_count": 0,
        "bookmark_count": 0,
        "highlight_count": 0,
        "commented_highlight_count": 0,
    }
    for session in sessions:
        for annotation in session.get("annotations") or []:
            counts["annotation_count"] += 1
            kind = profile_annotation_kind(annotation)
            if kind == "bookmark":
                counts["bookmark_count"] += 1
            elif kind == "highlight":
                counts["highlight_count"] += 1
            elif kind == "commented_highlight":
                counts["highlight_count"] += 1
                counts["commented_highlight_count"] += 1
    return counts


def increment_model_annotation_counts(summary: dict[str, int], annotation: Annotation) -> None:
    summary["annotations_created"] += 1
    if annotation.anchor_kind == Annotation.ANCHOR_KIND_BOOKMARK:
        summary["bookmarks_created"] += 1
        return
    summary["highlights_created"] += 1
    if annotation.comment_text:
        summary["commented_highlights_created"] += 1
