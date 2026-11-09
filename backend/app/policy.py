"""Source Permission Policy + Content Provenance (enforced in code, not just docs).

Principles (see docs/CONTENT_RIGHTS.md):
  * Permission is decided per Source, never per video or per platform.
  * Nothing reaches AI analysis unless `assert_analyzable()` passes.
  * A user's attestation is *recorded* and limits scope to private use; it is not treated as proof
    of platform-term compliance.
  * Prohibited acquisition methods (caption scraping, download+STT, unofficial APIs) cannot be selected.
  * CC license on a *video* is not permission to access YouTube captions; only an explicit
    transcript license on the transcript source counts.
"""
from dataclasses import dataclass
from datetime import timedelta

from .db import utcnow
from .models import Source


class AcquisitionMethod:
    USER_UPLOAD = "user_upload"
    USER_NOTE = "user_note"
    CREATOR_PROVIDED = "creator_provided"
    LICENSED_DISTRIBUTION = "licensed_distribution"
    CREATOR_OAUTH = "creator_oauth"
    PUBLIC_WEB = "public_web"
    PODCAST_RSS = "podcast_rss"
    EXTERNAL_PROVIDER = "external_provider"


ENABLED_METHODS = {
    AcquisitionMethod.USER_UPLOAD, AcquisitionMethod.USER_NOTE, AcquisitionMethod.CREATOR_PROVIDED,
    AcquisitionMethod.LICENSED_DISTRIBUTION, AcquisitionMethod.PUBLIC_WEB, AcquisitionMethod.PODCAST_RSS,
}
# Methods that are never allowed, whatever the user claims.
PROHIBITED_METHODS = {
    "youtube_caption_download", "video_download_stt", "scraping", "unofficial_api", "captcha_bypass",
}
# Connector interfaces exist but are not production paths.
DISABLED_CONNECTORS = {
    AcquisitionMethod.CREATOR_OAUTH: "Creator OAuth connector is not configured (needs a verified YouTube OAuth app).",
    AcquisitionMethod.EXTERNAL_PROVIDER: "Third-party transcript providers are disabled until their collection is legally verified.",
}
VERIFIED_EXTERNAL_PROVIDERS: set[str] = set()  # intentionally empty

# License identifiers that grant reuse of the *transcript text*. Value = scope.
OPEN_LICENSES = {
    "cc0-1.0": "open", "cc-by-4.0": "attribution_required", "cc-by-3.0": "attribution_required",
    "cc-by-sa-4.0": "attribution_share_alike", "cc-by-nc-4.0": "noncommercial_attribution",
    "public-domain": "open",
}
UNKNOWN_LICENSES = {"", "unknown", "none", "n/a", "all rights reserved", "youtube standard license"}


@dataclass
class Decision:
    status: str  # approved | pending | denied
    reason: str
    scope: str = ""

    @property
    def analyzable(self) -> bool:
        return self.status == "approved"


class PermissionDenied(Exception):
    def __init__(self, status: str, reason: str):
        super().__init__(reason)
        self.status, self.reason = status, reason


def normalize_license(lic: str) -> str:
    return (lic or "").strip().lower().replace(" ", "-").replace("_", "-") if (lic or "").strip().lower() not in UNKNOWN_LICENSES else ""


def evaluate_permission(
    method: str, *, license: str = "", rights_attested: bool = False, permission_evidence: str = "",
    source_url: str = "", provider: str = "",
) -> Decision:
    if method in PROHIBITED_METHODS:
        return Decision("denied", f"Acquisition method '{method}' is prohibited by project policy.")
    if method in DISABLED_CONNECTORS:
        if method == AcquisitionMethod.EXTERNAL_PROVIDER and provider in VERIFIED_EXTERNAL_PROVIDERS:
            pass
        else:
            return Decision("denied", DISABLED_CONNECTORS[method])
    if method not in ENABLED_METHODS:
        return Decision("denied", f"Unknown acquisition method '{method}'.")

    lic = normalize_license(license)

    if method == AcquisitionMethod.USER_NOTE:
        return Decision("approved", "User-authored note.", "private_analysis")

    if method == AcquisitionMethod.USER_UPLOAD:
        if not rights_attested:
            return Decision("denied", "You must confirm you have the right to process this file.")
        if not (lic or permission_evidence.strip()):
            return Decision("pending", "Describe your right to use this file (own content, license, permission). "
                                       "Attestation alone is recorded but not treated as verification.")
        return Decision("approved", "Approved for private analysis on user attestation; not verified, no redistribution.",
                        "private_analysis_user_attested")

    if method == AcquisitionMethod.CREATOR_PROVIDED:
        if len(permission_evidence.strip()) < 10:
            return Decision("pending", "Creator permission evidence (link or description of the grant) is required.")
        return Decision("approved", "Creator explicitly provided this transcript.", "creator_granted")

    # licensed_distribution / public_web / podcast_rss need a transcript-level open license or explicit grant
    if lic in OPEN_LICENSES:
        if not source_url.startswith("https://"):
            return Decision("pending", "A https URL for the licensed distribution is required for citation.")
        return Decision("approved", f"Transcript distributed under {license}.", OPEN_LICENSES[lic])
    if len(permission_evidence.strip()) >= 10 and method != AcquisitionMethod.LICENSED_DISTRIBUTION:
        return Decision("approved", "Explicit reuse permission documented for this source.", "documented_permission")
    return Decision("pending", "License is unknown or not an approved open license; not auto-approved.")


def assert_analyzable(source: Source) -> None:
    """Gate in front of the AI pipeline. Raises PermissionDenied unless the source is cleared."""
    if source.status != "approved":
        raise PermissionDenied(source.status, source.policy_reason or "Source is not approved.")
    if source.acquisition_method in PROHIBITED_METHODS:
        raise PermissionDenied("denied", "Prohibited acquisition method.")
    if not source.content:
        raise PermissionDenied("pending", "Source content is no longer available (retention expired or removed).")
    if source.retention_days and source.retrieved_at + timedelta(days=source.retention_days) < utcnow():
        raise PermissionDenied("denied", "Retention period expired; content must be re-supplied.")


def apply_decision(source: Source, d: Decision) -> None:
    source.status, source.policy_reason, source.permission_scope = d.status, d.reason, d.scope
