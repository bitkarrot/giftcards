---
status: issues
phase: 02-branded-delivery
depth: standard
files_reviewed: 7
findings:
  critical: 0
  warning: 2
  info: 5
  total: 7
---

# Code Review Report

## Scope

Post-session feature addition for the LNBits Gift Cards extension. Reviewed 7
files covering bg_color support for card templates, email background color for
the Fancy HTML template, edit dialog card design, detail dialog UX fixes,
bulk email no-emails dialog, single-column card design layout, and drag/resize
info banners.

## Findings

### CR-001 [Warning]
**File:** static/js/index.js:969-996
**Category:** Bug
**Description:** `openEditDialog` resets the card designer to defaults
(`resetCardDesigner()`) and immediately shows the dialog, then asynchronously
fetches the card's current design from the detail endpoint. If that fetch
fails (network error, 403, 500), the catch block at line 993 only logs the
error — the dialog remains open with default designer state (portrait
template, default positions). When the user clicks "Save Changes",
`saveCardEdit` (line 1076-1078) unconditionally includes
`design: this.buildDesignConfig()` in the PUT payload, which overwrites the
card's actual design with the default values. This is silent data loss: the
user may have only intended to edit the recipient name but ends up destroying
the card's template selection, QR position, text styling, and bg_color.
**Recommendation:** Either (a) disable the Save button until the design fetch
succeeds (track a `designLoaded` flag), or (b) skip sending the `design` field
in the PUT payload when the fetch failed (send only metadata fields), or (c)
show an error banner in the dialog and prevent save if the design could not be
loaded. Option (b) is the least invasive — only include `design` in the
payload when `applyDesignToDesigner` was successfully called.

### CR-002 [Warning]
**File:** static/js/index.js:1023-1048
**Category:** Bug
**Description:** `applyDesignToDesigner` does not restore the template preview
for custom templates. When `design.template_name === 'custom'` (line 1028),
it sets `this.selectedTemplate = 'custom'` and `this.templateAssetId` but
never reconstructs `this.templateUrl` from the asset ID, nor does it restore
`actualTemplateWidth/Height` or `previewWidth/Height` to the custom
template's dimensions. All of those remain at portrait defaults from
`resetCardDesigner()`. As a result:
- The preview shows the portrait template image instead of the custom upload.
- `bgColorEnabled` is false (correct for custom), but the QR/text drag
  positions are computed against portrait preview dimensions (212x325), so
  the fractions sent on save (`qrX / this.previewWidth`) will be wrong for the
  actual custom template dimensions.
- The user cannot accurately reposition elements because the preview does not
  match the real card.

This affects any card that was created with a custom uploaded template and
later edited.
**Recommendation:** For the `custom` branch, reconstruct the template URL
from the asset ID (`this.templateUrl = '/api/v1/assets/' + design.template_asset_id + '/data'`)
and fetch/restore the actual dimensions. If the original dimensions are not
available in the design response, consider storing them in the text_config
JSON at creation time, or fetch the asset metadata to recover them. At
minimum, set `templateUrl` so the preview image loads.

### CR-003 [Info]
**File:** services.py:70-86, views_api.py:558-574
**Category:** Quality
**Description:** The design-to-JSON serialization logic (splitting
DesignConfig into `qr_config` and `text_config` JSON columns) is duplicated
between `create_gift_card` (services.py:70-86) and `api_update_card`
(views_api.py:558-574). Both manually construct the two JSON dicts with
identical field lists. If a new DesignConfig field is added, both locations
must be updated in sync, and `_parse_design_config` (services.py:347-363)
must also be updated to read it back.
**Recommendation:** Extract a shared helper function (e.g.,
`serialize_design_config(design: DesignConfig) -> tuple[str, str]` returning
`(qr_config_json, text_config_json)`) in services.py and call it from both
locations. This ensures the round-trip stays consistent.

### CR-004 [Info]
**File:** static/js/index.js:372-405, 811-832, 998-1021
**Category:** Quality
**Description:** The card designer default-state reset logic is duplicated
three times: `resetCreateDialog` (line 372), `openBulkDialog` (line 811), and
`resetCardDesigner` (line 998). All three set the same 18 properties to the
same default values. `resetCardDesigner` was added for the edit dialog but
the other two were not refactored to call it.
**Recommendation:** Have `resetCreateDialog` and `openBulkDialog` call
`this.resetCardDesigner()` instead of duplicating the property assignments.
This reduces the maintenance surface to a single source of truth.

### CR-005 [Info]
**File:** models.py:33
**Category:** Security
**Description:** `DesignConfig.font_size` has no upper-bound validator. The
frontend slider limits font_size to 12-72, but the API accepts any positive
integer. A very large font_size (e.g., 100000) passed via a direct API call
would cause Pillow's `ImageFont.truetype` to allocate a large font bitmap,
potentially exhausting memory on the render endpoint. The render endpoint
(`/{token_hash}/image`) is public (no auth), but the design is only set via
authenticated endpoints (create/update require admin key), so an attacker
would need admin access to plant a malicious font_size. Risk is low but
non-zero.
**Recommendation:** Add a validator capping font_size at a reasonable maximum
(e.g., 200): `@validator("font_size") def _validate_font_size(cls, v): if v
< 8 or v > 200: raise ValueError(...); return v`.

### CR-006 [Info]
**File:** static/js/index.js:1050-1068
**Category:** Quality
**Description:** `buildDesignConfig` always includes
`bg_color: this.bgColor` regardless of whether `bgColorEnabled` is true
(i.e., even for custom templates where bg_color is not applicable). The
server correctly ignores bg_color for custom templates
(services.py:392: `template_name in ("portrait", "landscape")`), so this is
not a functional bug, but it sends a misleading field value. If the user
previously selected a bg_color with portrait, then switched to custom, the
stale bg_color is silently sent and stored in text_config JSON.
**Recommendation:** In `buildDesignConfig`, set `bg_color` to `null` when
`!this.bgColorEnabled` to avoid persisting an inapplicable value:
`bg_color: this.bgColorEnabled ? this.bgColor : null`.

### CR-007 [Info]
**File:** services.py:328-363
**Category:** Bug
**Description:** `_parse_design_config` constructs a `DesignConfig(...)`
from parsed JSON data (line 347) without catching `ValidationError`. If the
`text_config` or `qr_config` JSON in the database is corrupted (e.g.,
manually edited to contain `bg_color: "#GGGGGG"` or `qr_size: 10`), the
DesignConfig constructor raises a `ValidationError` that propagates up
through `render_card_image` and the public image endpoint, causing a 500
error. This is an existing pattern (font_color has the same exposure) and is
not introduced by the bg_color change, but bg_color adds another field that
could be corrupted. The M-6 comment on the validators says "validate hex
color so the public render endpoint cannot 500 on junk" — the validation
protects against API input but not against corrupted DB state.
**Recommendation:** Wrap the `DesignConfig(...)` construction in
`_parse_design_config` in a try/except that falls back to `defaults` on
`ValidationError`, with a warning log. This makes the render endpoint
resilient to DB-level corruption for all design fields.

## Summary

The bg_color feature is well-implemented across all layers. Hex color
validation is consistent and uses a strict regex (`^#[0-9A-Fa-f]{6}$`) at
every entry point (DesignConfig, DeliverRequest, CSVRow). Jinja2 autoescape
protects the fancy.html email template from XSS — the `{{ bg_color }}`
variable is interpolated into CSS `style` attributes but the regex validation
ensures only `#` + hex digits can reach the template, preventing CSS
injection. Path traversal defenses (allowlists for template_name, font_family,
text_align) remain intact. The cache-busting approach (`?t=Date.now()`) is
effective. The bulk email no-emails dialog correctly shows a warning instead
of a toast.

The two warnings (CR-001, CR-002) both relate to the edit dialog's handling of
existing card designs and could cause data loss or incorrect rendering for
cards with custom templates. They should be addressed before the feature is
considered production-ready.
