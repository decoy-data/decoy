"""Start one QA tester as its own pre-provisioned OS user (QA-BETA plan 5.1, 5.6 and 10a).

The owner runs `setup-testers.sh` once per node. The launcher never creates users and makes no
directory as the tester. It runs the tester's agent as `qatester-<slug>` with a clean environment:

- the tester starts in its own workspace (`<t>/work`, its HOME), never in the coordinator's folder;
- the bundle's `bin` folder is first on PATH. Before launch, as the tester, `realpath` of
  `command -v decoy` must sit under `realpath <t>/bundle`, and `decoy --version` must end with the
  version in `<t>/bundle/VERSION`, or the launch fails closed;
- stdout and stderr go to a coordinator-only capture file whose descriptor the central writer
  opens (`open_private_capture`), so this module never opens a file for writing itself;
- the tester submits into `<t>/work/inbox`, which the tester owns and `findings.py write` makes.
  The launcher lists it as the tester and fails closed when the listing exits nonzero. Capture and
  issued ids are coordinator-only. The coordinator gets one line of counts and finding ids, and a
  nonzero exit when the tester exited nonzero.

`<t>` is `/var/lib/decoy-qa/testers/qatester-<slug>`.

S3 notes. The checkout-read probe belongs to slice S3. After the probe shows, as the tester user on
this node, that a planted checkout read fails, S3 writes the marker file named by
`probe_marker_path(node, slug)` (default `/var/lib/decoy-qa/probes/<node>/<slug>.ok`) through
`publish_private_once`. The launcher refuses to start without it. S3 also registers the tester's
secret file content with the needles set.

Import dependency: the writer functions come from `scripts/qa/io.py` (slice S1a):
`publish_private_once(path, data)`, `make_private_dir(path, mode=0o700)` and
`open_private_capture(path) -> int`. This module loads that file by path only when no `IoApi` is
passed, and the load fails with a clear error until S1a lands. No product code is imported.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import secrets
import socket
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

USER_PREFIX = "qatester-"
SLUG = re.compile(r"[a-z0-9]{2,16}")
QA_ROOT = "/var/lib/decoy-qa"
SYSTEM_PATHS = {
    "linux": "/usr/local/bin:/usr/bin:/bin",
    "darwin": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
}
ID_PREFIX = "f-"
PROBE_MARKER_ROOT = Path("/var/lib/decoy-qa/probes")
FAULT_MARKER = "fault.ok"
BRIEFS = (
    "p1-solo-developer",
    "p2-data-engineer",
    "p3-ci-engineer",
    "p4-compliance-reviewer",
    "p5-careless-user",
    "checklist-pass",
    "doc-walk",
)
AGENT_BASE = ("claude", "-p")  # the brief goes in on stdin, never in argv
EXTRA_ARG = re.compile(r"--?[a-z][a-z-]{0,30}|[A-Za-z0-9._:/-]{1,60}")
EXTRA_DENY = re.compile(r"secret|token|passw|key|=", re.IGNORECASE)
BRIEF_DIR = Path(__file__).resolve().parents[2] / "docs" / "qa" / "briefs"


class LaunchError(Exception):
    """A launch input or the node is not ready. The message never holds data."""


@dataclass(frozen=True)
class IoApi:
    publish_private_once: Callable[[Path, bytes], None]
    make_private_dir: Callable[..., None]
    open_private_capture: Callable[[Path], int]


@dataclass(frozen=True)
class LaunchResult:
    line: str
    exit_code: int


Probe = Callable[[list[str]], tuple[int, str]]
Runner = Callable[[list[str], int, str], int]


def default_io() -> IoApi:
    path = Path(__file__).with_name("io.py")
    if not path.is_file():
        raise LaunchError("scripts/qa/io.py is missing: slice S1a must land first")
    spec = importlib.util.spec_from_file_location("_qa_io", path)
    if spec is None or spec.loader is None:
        raise LaunchError("scripts/qa/io.py cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    names = ("publish_private_once", "make_private_dir", "open_private_capture")
    funcs = [getattr(module, name, None) for name in names]
    if not all(callable(f) for f in funcs):
        raise LaunchError("scripts/qa/io.py lacks a writer the launcher needs")
    return IoApi(*funcs)


def _check_slug(slug: str) -> str:
    if not SLUG.fullmatch(slug):
        raise LaunchError("tester slug must be 2 to 16 lowercase letters or digits")
    return slug


def tester_user(slug: str) -> str:
    return USER_PREFIX + _check_slug(slug)


def tester_home(system: str, slug: str, qa_root: str | None = None) -> str:
    if system not in SYSTEM_PATHS:
        raise LaunchError("system must be linux or darwin")
    return f"{qa_root or QA_ROOT}/testers/{tester_user(slug)}"


def probe_marker_path(node: str, slug: str, root: Path = PROBE_MARKER_ROOT) -> Path:
    return root / node / f"{_check_slug(slug)}.ok"


def check_agent_extras(extra: Sequence[str]) -> list[str]:
    """Extra agent args go after the fixed argv. Each one is short, plain and secret-free."""
    for arg in extra:
        if not EXTRA_ARG.fullmatch(arg) or EXTRA_DENY.search(arg):
            raise LaunchError("an extra agent argument is not on the allowlist")
    return list(extra)


def build_command(
    *,
    system: str,
    slug: str,
    agent_argv: Sequence[str],
    ids: Sequence[str],
    findings_tool: str,
    qa_root: str | None = None,
    fault_dir: str | None = None,
) -> list[str]:
    """The full argv. The inner shell enters the tester's workspace before it runs the agent."""
    home = tester_home(system, slug, qa_root)
    work = f"{home}/work"
    env = [
        "env",
        "-i",
        f"HOME={work}",
        f"PATH={home}/bundle/bin:{SYSTEM_PATHS[system]}",
        f"DECOY_HOME={work}/.decoy-home",
        f"QA_TESTER={slug}",
        f"QA_INBOX={work}/inbox",
        f"QA_FINDING_IDS={','.join(ids)}",
        f"QA_FINDINGS_TOOL={findings_tool}",
    ]
    if slug == "p3":
        env.append(f"QA_SECRET_FILE={home}/secret/ci-secret")
    if fault_dir:
        env.append(f"QA_FAULT_DIR={fault_dir}")
    inner = ["sh", "-c", 'cd "$HOME" && exec "$@"', "sh", *agent_argv]
    return ["sudo", "-n", "-u", tester_user(slug), "-H", "--", *env, *inner]


def as_tester(system: str, slug: str, argv: Sequence[str], qa_root: str | None = None) -> list[str]:
    home = tester_home(system, slug, qa_root)
    env = ["env", "-i", f"HOME={home}/work", f"PATH={home}/bundle/bin:{SYSTEM_PATHS[system]}"]
    return ["sudo", "-n", "-u", tester_user(slug), "-H", "--", *env, *argv]


def allocate_ids(
    pass_dir: Path,
    slug: str,
    count: int,
    *,
    publish: Callable[[Path, bytes], None],
    token: Callable[[], str] = lambda: secrets.token_hex(6),
) -> list[str]:
    """Issue `count` ids for one tester, each reserved once through the private writer.

    An id is `f-<slug>-<random hex>` and holds nothing derived from data. A reserved name is
    skipped and a fresh token is drawn. `pass_dir/issued` must exist.
    """
    _check_slug(slug)
    ids: list[str] = []
    while len(ids) < count:
        candidate = f"{ID_PREFIX}{slug}-{token()}"
        try:
            publish(pass_dir / "issued" / candidate, b"")
        except FileExistsError:
            continue
        ids.append(candidate)
    return ids


def handback(
    slug: str,
    issued: Sequence[str],
    inbox_names: Sequence[str],
    *,
    exit_code: int,
    skipped: str = "",
) -> str:
    """One line of counts and ids. It reads file names only, never a record."""
    written = [i for i in issued if f"{i}.toml" in set(inbox_names)]
    tail = f" skipped={skipped}" if skipped else ""
    return (
        f"tester={slug} findings={len(written)} issued={len(issued)} "
        f"exit={exit_code}{tail} ids={','.join(written)}"
    )


def _probe(argv: list[str]) -> tuple[int, str]:
    done = subprocess.run(argv, capture_output=True, text=True, check=False, cwd="/")
    return done.returncode, done.stdout


def _run(argv: list[str], capture_fd: int, brief_text: str) -> int:
    return subprocess.run(
        argv,
        input=brief_text,
        text=True,
        stdout=capture_fd,
        stderr=capture_fd,
        check=False,
        cwd="/",
    ).returncode


def _fault_dir(system: str, slug: str, qa_root: str | None, probe: Probe) -> str | None:
    """The P5 bounded volume, if setup made it. The tester user checks, since the home is private."""
    if slug != "p5":
        return None
    t = tester_home(system, slug, qa_root)
    code, _ = probe(as_tester(system, slug, ["test", "-f", f"{t}/{FAULT_MARKER}"], qa_root))
    path = f"{t}/fault"
    return path if code == 0 else None


def launch(
    *,
    system: str,
    slug: str,
    brief: str,
    pass_dir: Path,
    id_count: int,
    findings_tool: str,
    extra_args: Sequence[str] = (),
    io: IoApi | None = None,
    runner: Runner = _run,
    probe: Probe = _probe,
    node: str | None = None,
    marker_root: Path = PROBE_MARKER_ROOT,
    qa_root: str | None = None,
    brief_dir: Path = BRIEF_DIR,
) -> LaunchResult:
    """Check the node, issue ids, run the tester with captured output, return the hand-back."""
    _check_slug(slug)
    if brief not in BRIEFS:
        raise LaunchError("unknown brief")
    extras = check_agent_extras(extra_args)
    if not probe_marker_path(node or socket.gethostname(), slug, marker_root).is_file():
        raise LaunchError("no S3 sandbox probe marker for this node and tester: run the probe")
    api = io or default_io()
    t = tester_home(system, slug, qa_root)

    # The tester resolves `decoy` inside its own bundle at the expected version, or nothing starts.
    check = 'p=$(command -v decoy) && realpath "$p" && realpath "$1" && "$p" --version && cat "$1/VERSION"'
    code, out = probe(as_tester(system, slug, ["sh", "-c", check, "sh", f"{t}/bundle"], qa_root))
    lines = out.splitlines()
    if (
        code != 0
        or len(lines) != 4
        or not lines[0].startswith(lines[1].rstrip("/") + "/")
        or not lines[3].strip()
        or lines[2].split()[-1:] != [lines[3].strip()]
    ):
        raise LaunchError("decoy does not resolve inside the tester's bundle at its version")

    # Capture and issued ids are coordinator-only. The tester's inbox is made by the tester.
    api.make_private_dir(pass_dir, mode=0o700)
    api.make_private_dir(pass_dir / "issued", mode=0o700)
    api.make_private_dir(pass_dir / "capture", mode=0o700)

    ids = allocate_ids(pass_dir, slug, id_count, publish=api.publish_private_once)
    fault = _fault_dir(system, slug, qa_root, probe)
    argv = build_command(
        system=system,
        slug=slug,
        agent_argv=[*AGENT_BASE, *extras],
        ids=ids,
        findings_tool=findings_tool,
        qa_root=qa_root,
        fault_dir=fault,
    )
    brief_text = (brief_dir / f"{brief}.md").read_text(encoding="utf-8")
    fd = api.open_private_capture(pass_dir / "capture" / f"{slug}.log")
    try:
        exit_code = runner(argv, fd, brief_text)
    finally:
        os.close(fd)
    list_inbox = 'if [ -d "$1" ]; then ls -1 "$1"; fi'
    code, listing = probe(
        as_tester(system, slug, ["sh", "-c", list_inbox, "sh", f"{t}/work/inbox"], qa_root)
    )
    if code != 0:
        raise LaunchError("the tester inbox could not be listed")
    skipped = "disk-full" if slug == "p5" and fault is None else ""
    line = handback(slug, ids, listing.split(), exit_code=exit_code, skipped=skipped)
    return LaunchResult(line, exit_code)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Start one QA tester (see docs/qa/beta-program.md)."
    )
    parser.add_argument("slug", help="tester slug, for example p1 or checklist")
    parser.add_argument("--brief", required=True, choices=BRIEFS)
    parser.add_argument("--pass-dir", type=Path, required=True)
    parser.add_argument("--ids", type=int, default=20, help="finding ids to issue")
    parser.add_argument("--findings-tool", default="/opt/decoy-qa/findings.py")
    parser.add_argument("extra", nargs="*", help="extra agent arguments, allowlisted")
    args = parser.parse_args(argv)
    system = "darwin" if sys.platform == "darwin" else "linux"
    try:
        result = launch(
            system=system,
            slug=args.slug,
            brief=args.brief,
            pass_dir=args.pass_dir,
            id_count=args.ids,
            findings_tool=args.findings_tool,
            extra_args=args.extra,
        )
    except LaunchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(result.line)
    return 1 if result.exit_code != 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
