from __future__ import annotations

from typing import Any

from rest_framework import serializers

from .models import (
    HIGHLIGHT_COLOR_TOKENS,
    HIGHLIGHT_COLOR_YELLOW,
    SELECTOR_KIND_EPUB_CFI,
    Annotation,
)
from .profile import EPUB_CFI_CONFORMS_TO
from .w3c import build_publication_source


def compact_annotation_from_profile(
    *, motivations: list[str], target: dict[str, Any], body: list[dict[str, Any]]
) -> dict[str, str]:

    selector = target.get("selector")
    selector_value: str = ""
    quote_exact: str = ""
    quote_prefix: str = ""
    quote_suffix: str = ""

    if isinstance(selector, dict):
        raw_value = selector.get("value")
        if isinstance(raw_value, str) and raw_value:
            selector_value = raw_value
        elif raw_value is not None and raw_value != "":
            selector_value = str(raw_value)
    elif isinstance(selector, list):
        for item in selector:
            if not isinstance(item, dict):
                continue
            stype = item.get("type")
            if stype == "TextQuoteSelector":
                raw_exact = item.get("exact")
                if isinstance(raw_exact, str) and raw_exact.strip() and not quote_exact:
                    quote_exact = raw_exact
                    raw_prefix = item.get("prefix")
                    raw_suffix = item.get("suffix")
                    quote_prefix = raw_prefix if isinstance(raw_prefix, str) else ""
                    quote_suffix = raw_suffix if isinstance(raw_suffix, str) else ""
            elif stype in (None, "FragmentSelector"):
                raw_value = item.get("value")
                if selector_value:
                    continue
                if isinstance(raw_value, str) and raw_value:
                    selector_value = raw_value
                elif raw_value is not None and raw_value != "":
                    selector_value = str(raw_value)

    highlight_text: str = ""
    highlight_color: str = ""
    comment_text: str = ""

    for b in body or []:
        if not isinstance(b, dict):
            continue
        if b.get("type") != "TextualBody":
            continue
        purpose = str(b.get("purpose") or "").strip()
        raw_value = b.get("value")
        value: str = raw_value if isinstance(raw_value, str) else ""
        raw_color = b.get("color")
        color: str = raw_color if isinstance(raw_color, str) else ""

        if purpose in ("highlighting", "describing") and (value or color):
            if not highlight_text:
                highlight_text = value
            if not highlight_color and color:
                highlight_color = color.strip()
        elif purpose == "commenting" and value:
            if not comment_text:
                comment_text = value

    motivations_set = {m.strip() for m in motivations if isinstance(m, str)}
    if Annotation.MOTIVATION_BOOKMARKING in motivations_set and (
        Annotation.MOTIVATION_HIGHLIGHTING in motivations_set
        or Annotation.MOTIVATION_COMMENTING in motivations_set
    ):
        raise serializers.ValidationError({"motivation": "Invalid motivation combination."})

    if Annotation.MOTIVATION_BOOKMARKING in motivations_set:
        anchor_kind = Annotation.ANCHOR_KIND_BOOKMARK
    else:
        anchor_kind = Annotation.ANCHOR_KIND_HIGHLIGHT

    if quote_exact:
        if highlight_text and highlight_text != quote_exact:
            raise serializers.ValidationError(
                {"target": "TextQuoteSelector.exact must match describing body value."}
            )
        if not highlight_text:
            highlight_text = quote_exact

    if anchor_kind == Annotation.ANCHOR_KIND_BOOKMARK:
        if highlight_text or highlight_color or comment_text or quote_prefix or quote_suffix:
            raise serializers.ValidationError(
                {"detail": "Bookmarks cannot include highlight/comment/quote context payload."}
            )

    if anchor_kind == Annotation.ANCHOR_KIND_HIGHLIGHT:
        if not highlight_text.strip():
            # Standalone comment-only annotations are not supported.
            raise serializers.ValidationError(
                {"detail": "Highlights require describing body text (selected text)."}
            )

    if highlight_text or highlight_color:
        if not highlight_color:
            highlight_color = HIGHLIGHT_COLOR_YELLOW
        elif highlight_color not in HIGHLIGHT_COLOR_TOKENS:
            raise serializers.ValidationError(
                {"body": "Unsupported highlight color token."}
            )

    return {
        "anchor_kind": anchor_kind,
        "selector_kind": SELECTOR_KIND_EPUB_CFI,
        "selector_value": selector_value,
        "highlight_text": highlight_text,
        "quote_prefix": quote_prefix,
        "quote_suffix": quote_suffix,
        "highlight_color": highlight_color,
        "comment_text": comment_text,
    }


def annotation_profile_representation(instance: Annotation, data: dict[str, Any]) -> dict[str, Any]:

    motivations: list[str]
    if instance.anchor_kind == Annotation.ANCHOR_KIND_BOOKMARK:
        motivations = [Annotation.MOTIVATION_BOOKMARKING]
    else:
        motivations = [Annotation.MOTIVATION_HIGHLIGHTING]
        if (instance.comment_text or "").strip():
            motivations.append(Annotation.MOTIVATION_COMMENTING)
    data["motivation"] = motivations

    fragment: dict[str, str] = {"value": instance.selector_value}
    if instance.selector_kind == SELECTOR_KIND_EPUB_CFI:
        fragment["type"] = "FragmentSelector"
        fragment["conformsTo"] = EPUB_CFI_CONFORMS_TO
    else:
        # Safety fallback: avoid crashing list/detail if a bad row exists.
        fragment["type"] = "UnknownSelector"

    source = build_publication_source(book=instance.book)
    selector_out: object = fragment
    if (
        instance.highlight_text
        and (getattr(instance, "quote_prefix", "") or getattr(instance, "quote_suffix", ""))
    ):
        quote: dict[str, str] = {"type": "TextQuoteSelector", "exact": instance.highlight_text}
        if getattr(instance, "quote_prefix", ""):
            quote["prefix"] = instance.quote_prefix
        if getattr(instance, "quote_suffix", ""):
            quote["suffix"] = instance.quote_suffix
        selector_out = [fragment, quote]

    data["target"] = {"source": source, "selector": selector_out}

    bodies: list[dict] = []
    if instance.highlight_text or instance.highlight_color:
        b: dict = {"type": "TextualBody", "purpose": "describing", "value": instance.highlight_text or ""}
        # Color token is part of the stable highlight contract; default to yellow.
        b["color"] = (instance.highlight_color or HIGHLIGHT_COLOR_YELLOW)
        bodies.append(b)
    if instance.comment_text:
        bodies.append(
            {"type": "TextualBody", "purpose": "commenting", "value": instance.comment_text}
        )
    data["body"] = bodies
    return data
