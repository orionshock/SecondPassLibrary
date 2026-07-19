from pathlib import Path

import pytest


pytestmark = [pytest.mark.product_ui, pytest.mark.static_contract]


def test_server_settings_tabs_are_external_and_use_product_language():
    template = Path("web/templates/web/server/settings.html").read_text(
        encoding="utf-8"
    )

    assert 'id="server-settings-card"' not in template
    assert 'id="server-settings-root" class="server-settings-root" data-tab-root' in template
    assert 'class="server-settings-nav-row"' in template
    general = template.index(">General</button>")
    public = template.index(">Public Library</button>")
    groups = template.index(">Library Groups</button>")
    assert general < public < groups
    assert ">Dashboard</button>" not in template
    assert 'id="server-settings-panel-dashboard"' not in template
    assert template.index('class="tabs server-settings-tabs"') < template.index(
        'id="server-settings-form"'
    )


def test_general_public_and_groups_panels_keep_meaningful_cards_and_fields():
    template = Path("web/templates/web/server/settings.html").read_text(
        encoding="utf-8"
    )

    identity_panel = template.split('id="server-settings-panel-identity"', 1)[1].split(
        'id="server-settings-panel-public"', 1
    )[0]
    assert "Server identity" in identity_panel
    assert ">Banner</h2>" in identity_panel
    for field_id in (
        "server-settings-name-input",
        "server-settings-description-input",
        "server-settings-banner-input",
    ):
        assert f'id="{field_id}"' in identity_panel

    public_panel = template.split('id="server-settings-panel-public"', 1)[1].split(
        'id="server-settings-panel-library-groups"', 1
    )[0]
    assert "server-settings-public-name-input" in public_panel
    assert "server-settings-public-description-input" in public_panel
    assert "Turning this off later requires the Service Hatch" in template


def test_server_settings_help_uses_accessible_product_popovers_without_titles():
    template = Path("web/templates/web/server/settings.html").read_text(
        encoding="utf-8"
    )
    css = Path("web/static/web/css/product.css").read_text(encoding="utf-8")

    assert template.count('class="server-settings-help-button"') == 4
    assert template.count('class="server-settings-help-popover" role="tooltip"') == 4
    assert template.count('aria-describedby="server-settings-') == 4
    assert "server-settings-help-button\" title=" not in template
    assert ".server-settings-help-button:hover .server-settings-help-popover" in css
    assert ".server-settings-help-button:focus .server-settings-help-popover" in css
    assert "opacity: 0" in css


def test_library_groups_states_follow_description_with_outlined_pill_and_confirm_enable():
    template = Path("web/templates/web/server/settings.html").read_text(
        encoding="utf-8"
    )
    source = Path("web/static/web/js/server/settings.js").read_text(encoding="utf-8")
    css = Path("web/static/web/css/product.css").read_text(encoding="utf-8")

    description = template.index("Create separate library spaces")
    state = template.index('class="server-settings-feature-state"')
    pill = template.index('id="server-settings-advanced-groups-display"')
    detail = template.index('id="server-settings-advanced-groups-enabled"')
    assert description < state < pill < detail
    assert "server-settings-feature-state--enabled" not in template
    assert "server-settings-feature-state--disabled" not in template
    assert "server-settings-feature-action" in template
    assert "margin: 14px 12px 4px" in css
    assert "padding-left: 12px" in css
    assert ".server-settings-display--status.is-enabled" in css
    assert ".server-settings-display--status.is-disabled" in css
    assert "margin-top: 14px" in css
    assert 'classList.toggle("is-enabled", advancedGroups)' in source
    assert 'classList.toggle("is-disabled", !advancedGroups)' in source
    assert "window.confirm(" in source
    assert "data-confirm-message=" in template


def test_service_hatch_help_uses_the_accessible_product_popover():
    template = Path("web/templates/web/server/settings.html").read_text(
        encoding="utf-8"
    )

    assert template.count('aria-label="Service Hatch help"') == 2
    assert "server-settings-disabled-service-hatch-help" in template
    assert "server-settings-enabled-service-hatch-help" in template
    assert "Advanced settings and recovery tools provided through Django Admin." in template
    assert 'title="' not in template


def test_view_values_empty_style_and_edit_controls_remain_bounded():
    source = Path("web/static/web/js/server/settings.js").read_text(encoding="utf-8")
    css = Path("web/static/web/css/product.css").read_text(encoding="utf-8")

    assert 'setText(element, empty ? "(empty)" : value)' in source
    assert 'element.classList.toggle("server-settings-display--empty", empty)' in source
    assert ".server-settings-display--empty" in css
    assert "width: min(100%, 760px)" in css
    assert "width: min(100%, 640px)" in css
    assert ".server-settings-actions" in css
    assert "margin-left: auto" in css


def test_server_settings_save_payload_and_behavior_routes_are_unchanged():
    source = Path("web/static/web/js/server/settings.js").read_text(encoding="utf-8")

    assert 'initTabs($("#server-settings-root"))' in source
    for assignment in (
        "payload.server_name = server_name",
        "payload.server_description = server_description",
        "payload.server_banner_message = server_banner_message",
        "payload.public_group_name = publicNameInput ? publicNameInput.value : \"\"",
        "payload.public_group_description = publicDescInput ? publicDescInput.value : \"\"",
    ):
        assert assignment in source
    assert 'patchJSON("/api/v1/server/settings/", payload)' in source
    assert '"/api/v1/server/settings/advanced-library-groups/enable/"' in source


def test_server_settings_tabs_scope_buttons_and_sibling_panels_to_the_same_root():
    template = Path("web/templates/web/server/settings.html").read_text(
        encoding="utf-8"
    )
    tabs = Path("web/static/web/js/ui/tabs.js").read_text(encoding="utf-8")

    assert "data-tab-root" in template
    assert 'group.closest("[data-tab-root]")' in tabs
    assert 'data-tab="public-library"' in template
    assert 'data-tab-panel="public-library"' in template
