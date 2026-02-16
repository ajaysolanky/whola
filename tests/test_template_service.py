import pytest

from template_service import TemplateError, inject_chat_module, load_brand_config, render_campaign_templates


def test_render_campaign_templates_no_unresolved_tokens():
    brand = load_brand_config("acme")
    rendered = render_campaign_templates(
        brand,
        campaign={"subject": "Spring Sale"},
        recipient={"email": "demo@example.com", "first_name": "Sam"},
        chat_endpoint="https://example.com/api/v1/chat/message",
        token="token-123",
    )

    assert "{{CHAT_MODULE_SLOT}}" not in rendered["amp_html"]
    assert "__COLOR_PRIMARY__" not in rendered["amp_html"]
    assert brand["color_primary"] in rendered["amp_html"]
    assert "token-123" in rendered["amp_html"]


def test_injection_fails_without_slot():
    with pytest.raises(TemplateError):
        inject_chat_module("<html><body>No slot</body></html>", "<div>chat</div>")
