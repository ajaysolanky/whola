from __future__ import annotations

from copy import deepcopy


DEFAULT_PRESET_ID = "spring_drop"

_PRESETS = {
    "spring_drop": {
        "id": "spring_drop",
        "label": "Spring New Arrivals",
        "subject": "New spring arrivals are here",
        "preheader": "Fresh styles just dropped. Ask our AI rep for fit and recommendations.",
        "hero_eyebrow": "Spring Collection 2026",
        "hero_headline": "Find your perfect spring setup",
        "hero_body": "Shop lightweight layers, weather-ready essentials, and limited-run colorways picked for this season.",
        "offer_badge": "Limited Drop",
        "cta_label": "Shop New Arrivals",
        "feature_1": "Lightweight, breathable materials for variable weather",
        "feature_2": "Early-access colorways available this week only",
        "feature_3": "Free shipping on orders over $75",
    },
    "vip_launch": {
        "id": "vip_launch",
        "label": "VIP Early Access",
        "subject": "VIP early access is open",
        "preheader": "You get first pick before public launch. Chat in-email for product guidance.",
        "hero_eyebrow": "VIP ACCESS",
        "hero_headline": "Your early-access window is live",
        "hero_body": "We reserved our best inventory for VIP members first. Get recommendations and sizing help right inside this email.",
        "offer_badge": "Members Only",
        "cta_label": "Unlock VIP Picks",
        "feature_1": "Members-only inventory before public release",
        "feature_2": "Personalized product matching from the AI rep",
        "feature_3": "Priority support for returns and exchanges",
    },
    "clearance_event": {
        "id": "clearance_event",
        "label": "Clearance Campaign",
        "subject": "Final markdowns up to 60% off",
        "preheader": "Last chance on top sellers. Ask the AI rep what is still in stock.",
        "hero_eyebrow": "Final Markdown Event",
        "hero_headline": "Save up to 60% while inventory lasts",
        "hero_body": "We are clearing seasonal inventory. Stock is moving fast, so ask in-email for availability and alternatives.",
        "offer_badge": "Up to 60% Off",
        "cta_label": "Shop Clearance",
        "feature_1": "Top categories discounted through end of week",
        "feature_2": "Low-stock alerts available via in-email chat",
        "feature_3": "Free returns within 30 days",
    },
}


def list_presets() -> list[dict[str, str]]:
    return [deepcopy(_PRESETS[key]) for key in sorted(_PRESETS.keys())]


def get_preset(preset_id: str | None) -> dict[str, str]:
    if preset_id and preset_id in _PRESETS:
        return deepcopy(_PRESETS[preset_id])
    return deepcopy(_PRESETS[DEFAULT_PRESET_ID])
