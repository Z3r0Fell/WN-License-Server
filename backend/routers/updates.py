"""Update-channel manifest endpoint for the WatchNexus media server.

The desktop/app client (`UpdateController.CheckForUpdates`) falls back to
``GET /api/updates/manifest`` when the GitHub Updates/ channel has no
``latest.json``. This serves a tier-aware manifest that admins can edit from
the runtime settings (category "updates") without redeploying.

Supported fields (mirrors the GitHub Updates/latest.json schema the client
parses):
  latest_version, release_date, release_notes, changelog, download_url,
  size_mb, mandatory, min_version.
"""
from fastapi import APIRouter

import runtime_settings

router = APIRouter(tags=["updates"])

TIER_DOWNLOAD_PREFIXES = {
    "standard": "https://github.com/WN-Admin/WatchNexus/blob/main/Releases",
    "pro": "https://github.com/WN-Admin/WatchNexus/blob/main/Releases",
    "ultra": "https://github.com/WN-Admin/WatchNexus/blob/main/Releases",
}


def _manifest_for_tier(tier: str) -> dict:
    """Build the manifest, preferring admin-editable runtime settings."""
    return {
        "latest_version": runtime_settings.get("UPDATES_LATEST_VERSION") or "1.0.0",
        "release_date": runtime_settings.get("UPDATES_RELEASE_DATE"),
        "release_notes": runtime_settings.get("UPDATES_RELEASE_NOTES"),
        "changelog": runtime_settings.get("UPDATES_CHANGELOG"),
        "download_url": runtime_settings.get("UPDATES_DOWNLOAD_URL")
            or TIER_DOWNLOAD_PREFIXES.get(tier, TIER_DOWNLOAD_PREFIXES["standard"]),
        "size_mb": _as_float(runtime_settings.get("UPDATES_SIZE_MB")),
        "mandatory": runtime_settings.get("UPDATES_MANDATORY") in (True, "true", "1"),
        "min_version": runtime_settings.get("UPDATES_MIN_VERSION") or "1.0.0",
    }


def _as_float(value):
    try:
        return float(value) if value not in (None, "") else 0.0
    except (TypeError, ValueError):
        return 0.0


@router.get("/updates/manifest")
async def updates_manifest(tier: str = "standard", current: str = "1.0.0"):
    return _manifest_for_tier(tier)
