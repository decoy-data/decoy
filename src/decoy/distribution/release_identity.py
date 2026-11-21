"""The one release-identity fact: which repos, site and download host a release names.

Every other module imports these values instead of spelling them. The shell installers run
before Python exists, so `install.sh` and `install.ps1` carry checked copies; the sentry in
`tests/sentry/release/test_release_identity_sentry.py` keeps them equal to this file.

Comparisons against these values are exact equality. Prefix, suffix, case-fold and `$`
anchored matches are not used, so a fork, a renamed repo or a value with a trailing newline
is refused.
"""

from __future__ import annotations

import re
from datetime import date
from urllib.parse import urlsplit

CLI_REPO = "decoy-data/decoy"
ENGINE_REPO = "decoy-data/decoy-engine"
WEB_REPO = "decoy-data/decoy-web"
SITE_ORIGIN = "https://trydecoy.com"

# Layout of every artifact URL: <ARTIFACT_BASE>/v<version>/<name>.
ARTIFACT_BASE = "https://github.com/decoy-data/decoy/releases/download"
# A GitHub origin for artifacts is refused unless this names a dated owner decision.
ARTIFACT_HOST_EXCEPTION: str | None = (
    "owner 2026-11-18: V1 bundles are GitHub Release assets of decoy-data/decoy, "
    "a dated exception to the 2026-11-12 static site plus CDN decision"
)

# The author and committer of a decoy-web commit, as `git log` prints them: %an %ae %cn %ce.
WEB_COMMIT_IDENTITY = ("ckeep", "decoy@trydecoy.com", "ckeep", "decoy@trydecoy.com")

_GITHUB_HOSTS = frozenset({"github.com", "githubusercontent.com"})
_DECISION = re.compile(r"owner (\d{4}-\d{2}-\d{2})[: ] ?\S.{9,}", re.DOTALL)


class ReleaseIdentityError(ValueError):
    """A release fact broke the identity rule. The message is a fixed code."""


def artifact_url(version: str, name: str, base: str = ARTIFACT_BASE) -> str:
    """The one place an artifact URL is built: `<base>/v<version>/<name>`."""
    return f"{base}/v{version}/{name}"


def _is_github_host(host: str) -> bool:
    host = host.lower()
    return host in _GITHUB_HOSTS or host.endswith(".githubusercontent.com")


def _dated_owner_decision(text: object) -> bool:
    if not isinstance(text, str):
        return False
    match = _DECISION.fullmatch(text)
    if match is None:
        return False
    try:
        date.fromisoformat(match.group(1))
    except ValueError:
        return False
    return True


def check_artifact_origin(base: str, exception: str | None) -> None:
    """Refuse an artifact base that is not https, or is on GitHub with no dated owner exception."""
    parts = urlsplit(base)
    if parts.scheme != "https" or not parts.hostname:
        raise ReleaseIdentityError("release_identity_mismatch")
    if _is_github_host(parts.hostname) and not _dated_owner_decision(exception):
        raise ReleaseIdentityError("release_identity_mismatch")


def validate() -> None:
    """Check the shipped values. Signing commands call this before they load a key."""
    check_artifact_origin(ARTIFACT_BASE, ARTIFACT_HOST_EXCEPTION)
