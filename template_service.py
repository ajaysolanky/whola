from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app_config import BASE_DIR
from models import Brand


BRAND_CONFIG_DIR = BASE_DIR / "config" / "brands"
TEMPLATE_BASE_DIR = BASE_DIR / "templates" / "base"
TEMPLATE_MODULE_DIR = BASE_DIR / "templates" / "modules"

REQUIRED_BRAND_FIELDS = {
    "brand_id",
    "brand_name",
    "logo_url",
    "font_stack",
    "color_primary",
    "color_surface",
    "color_text",
    "color_muted",
    "border_radius_px",
    "spacing_scale",
    "chat_header_title",
}

HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class TemplateError(Exception):
    pass


def _read_file(path: Path) -> str:
    if not path.exists():
        raise TemplateError(f"Template not found: {path}")
    return path.read_text(encoding="utf-8")


def _replace_tokens(template: str, mapping: dict[str, str]) -> str:
    result = template
    for key, value in mapping.items():
        result = result.replace(f"__{key}__", value)
    unresolved = re.findall(r"__[A-Z0-9_]+__", result)
    if unresolved:
        raise TemplateError(f"Unresolved template tokens: {sorted(set(unresolved))}")
    return result


def validate_brand_config(config: dict[str, Any]) -> None:
    missing = REQUIRED_BRAND_FIELDS - set(config.keys())
    if missing:
        raise TemplateError(f"Missing brand config fields: {sorted(missing)}")

    for field in ["color_primary", "color_surface", "color_text", "color_muted"]:
        if not HEX_COLOR_RE.match(str(config[field])):
            raise TemplateError(f"Invalid hex color for {field}: {config[field]}")

    if not str(config["font_stack"]).strip():
        raise TemplateError("font_stack must be non-empty")

    if not str(config["logo_url"]).strip().startswith(("https://", "http://")):
        raise TemplateError("logo_url must be an absolute URL")

    if int(config["border_radius_px"]) < 0:
        raise TemplateError("border_radius_px must be >= 0")

    if int(config["spacing_scale"]) < 0:
        raise TemplateError("spacing_scale must be >= 0")


def load_brand_config(brand_id: str) -> dict[str, Any]:
    path = BRAND_CONFIG_DIR / f"{brand_id}.json"
    if not path.exists():
        raise TemplateError(f"Brand config not found for brand_id={brand_id}")
    data = json.loads(path.read_text(encoding="utf-8"))
    validate_brand_config(data)
    return data


def load_all_brand_configs() -> list[dict[str, Any]]:
    configs: list[dict[str, Any]] = []
    for path in sorted(BRAND_CONFIG_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        validate_brand_config(data)
        configs.append(data)
    return configs


def sync_brands_table(db_session) -> None:
    configs = load_all_brand_configs()
    for cfg in configs:
        existing = db_session.query(Brand).filter_by(brand_id=cfg["brand_id"]).one_or_none()
        config_path = str(BRAND_CONFIG_DIR / f"{cfg['brand_id']}.json")
        if existing is None:
            db_session.add(
                Brand(
                    brand_id=cfg["brand_id"],
                    name=cfg["brand_name"],
                    config_path=config_path,
                )
            )
        else:
            existing.name = cfg["brand_name"]
            existing.config_path = config_path
    db_session.commit()


def inject_chat_module(base_template: str, module_markup: str) -> str:
    slot = "{{CHAT_MODULE_SLOT}}"
    if slot not in base_template:
        raise TemplateError("Base template is missing {{CHAT_MODULE_SLOT}}")
    return base_template.replace(slot, module_markup)


def render_amp_module(brand_cfg: dict[str, Any], chat_endpoint: str, token: str, convo_id: str = "") -> str:
    module = _read_file(TEMPLATE_MODULE_DIR / "amp_chat_module.html")
    return _replace_tokens(
        module,
        {
            "CHAT_ENDPOINT": chat_endpoint,
            "CHAT_TOKEN": token,
            "CONVO_ID": convo_id,
            "CHAT_HEADER_TITLE": str(brand_cfg["chat_header_title"]),
        },
    )


def render_campaign_templates(
    brand_cfg: dict[str, Any],
    campaign: dict[str, str],
    recipient: dict[str, str],
    chat_endpoint: str,
    token: str,
    convo_id: str = "",
) -> dict[str, str]:
    amp_base = _read_file(TEMPLATE_BASE_DIR / "amp_campaign_base.html")
    html_fallback = _read_file(TEMPLATE_BASE_DIR / "html_fallback_base.html")

    amp_module = render_amp_module(brand_cfg, chat_endpoint=chat_endpoint, token=token, convo_id=convo_id)
    amp_with_module = inject_chat_module(amp_base, amp_module)

    campaign_content = {
        "subject": campaign.get("subject", "Campaign update"),
        "preheader": campaign.get(
            "preheader",
            "This campaign includes an interactive AI chat experience in AMP-capable inboxes.",
        ),
        "hero_eyebrow": campaign.get("hero_eyebrow", "Featured Campaign"),
        "hero_headline": campaign.get("hero_headline", campaign.get("subject", "Campaign update")),
        "hero_body": campaign.get(
            "hero_body",
            "we picked these highlights for you and can answer questions instantly in your inbox.",
        ),
        "offer_badge": campaign.get("offer_badge", "Featured"),
        "cta_label": campaign.get("cta_label", "Explore Now"),
        "feature_1": campaign.get("feature_1", "Curated picks tailored for this campaign"),
        "feature_2": campaign.get("feature_2", "Fast answers from an embedded AI product rep"),
        "feature_3": campaign.get("feature_3", "Simple in-email support for purchase questions"),
    }

    token_map = {
        "BRAND_NAME": str(brand_cfg["brand_name"]),
        "BRAND_LOGO_URL": str(brand_cfg["logo_url"]),
        "FONT_STACK": str(brand_cfg["font_stack"]),
        "COLOR_PRIMARY": str(brand_cfg["color_primary"]),
        "COLOR_SURFACE": str(brand_cfg["color_surface"]),
        "COLOR_TEXT": str(brand_cfg["color_text"]),
        "COLOR_MUTED": str(brand_cfg["color_muted"]),
        "BORDER_RADIUS_PX": str(brand_cfg["border_radius_px"]),
        "SPACING_SCALE": str(brand_cfg["spacing_scale"]),
        "CAMPAIGN_SUBJECT": campaign_content["subject"],
        "CAMPAIGN_PREHEADER": campaign_content["preheader"],
        "HERO_EYEBROW": campaign_content["hero_eyebrow"],
        "HERO_HEADLINE": campaign_content["hero_headline"],
        "HERO_BODY": campaign_content["hero_body"],
        "OFFER_BADGE": campaign_content["offer_badge"],
        "CTA_LABEL": campaign_content["cta_label"],
        "FEATURE_1": campaign_content["feature_1"],
        "FEATURE_2": campaign_content["feature_2"],
        "FEATURE_3": campaign_content["feature_3"],
        "RECIPIENT_FIRST_NAME": recipient.get("first_name", "there"),
    }

    amp_html = _replace_tokens(amp_with_module, token_map)
    html_html = _replace_tokens(html_fallback, token_map)
    text_body = (
        f"Hi {recipient.get('first_name', 'there')},\n\n"
        f"{campaign_content['subject']}\n\n"
        "This email contains an interactive AMP chat experience in compatible inboxes."
    )

    return {
        "amp_html": amp_html,
        "html_html": html_html,
        "text_body": text_body,
        "amp_module": amp_module,
    }
