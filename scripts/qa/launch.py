"""Start one QA tester as its own pre-provisioned OS user (QA-BETA plan 5.1, 5.6).

The launcher never creates users: the owner runs `setup-testers.sh` once per node. It builds one
command that runs the tester's agent as `qatester-<slug>` with a clean environment, whose home
holds only the bundle, a docs copy and a read-only corpus mount. Stdout and stderr go to a
node-local capture file through a shell redirect, so this module never opens a file for writing
and the tester never sees the capture. All files are published through the private writer in
`scripts/qa/io.py` (`publish_private_once`), taken as a function argument. The coordinator gets
back one line of counts and finding ids.

Import dependency: this module loads `io.py` from its own folder by path, only when no writer
is passed. Until slice S1a lands, that load fails with a clear error. Tests pass their own
writer. The module imports no product code.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import secrets
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

Writer = Callable[[Path, bytes], None]

USER_PREFIX = "qatester-"
SLUG = re.compile(r"[a-z0-9]{2,16}")
HOME_ROOTS = {"linux": "/home", "darwin": "/Users"}
SYSTEM_PATHS = {
    "linux": "/usr/local/bin:/usr/bin:/bin",
    "darwin": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
}
ID_PREFIX = "f-"


class LaunchError(Exception):
    """A launch input is invalid. The message never holds data."""


def _check_slug(slug: str) -> str:
    if not SLUG.fullmatch(slug):
        raise LaunchError("tester slug must be 2 to 16 lowercase letters or digits")
    return slug


def tester_user(slug: str) -> str:
    return USER_PREFIX + _check_slug(slug)


def tester_home(system: str, slug: str) -> str:
    if system not in HOME_ROOTS:
        raise LaunchError("system must be linux or darwin")
    return f"{HOME_ROOTS[system]}/{tester_user(slug)}"


def build_command(
    *,
    system: str,
    slug: str,
    agent_argv: Sequence[str],
    pass_dir: Path,
    capture_path: Path,
    ids: Sequence[str],
    findings_tool: str,
) -> list[str]:
    """The full argv. The outer `sh` is the coordinator, so it owns the capture file."""
    home = tester_home(system, slug)
    env = [
        "env",
        "-i",
        f"HOME={home}",
        f"PATH={SYSTEM_PATHS[system]}",
        f"DECOY_HOME={home}/.decoy-home",
        f"QA_TESTER={slug}",
        f"QA_PASS_DIR={pass_dir}",
        f"QA_FINDING_IDS={','.join(ids)}",
        f"QA_FINDINGS_TOOL={findings_tool}",
    ]
    inner = ["sudo", "-n", "-u", tester_user(slug), "-H", "--", *env, *agent_argv]
    return ["sh", "-c", 'exec "$@" >>"$0" 2>&1', str(capture_path), *inner]


def _default_writer() -> Writer:
    path = Path(__file__).with_name("io.py")
    if not path.is_file():
        raise LaunchError("scripts/qa/io.py is missing: slice S1a must land first")
    spec = importlib.util.spec_from_file_location("_qa_io", path)
    if spec is None or spec.loader is None:
        raise LaunchError("scripts/qa/io.py cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.publish_private_once  # type: ignore[no-any-return]


def allocate_ids(
    pass_dir: Path,
    slug: str,
    count: int,
    *,
    writer: Writer,
    token: Callable[[], str] = lambda: secrets.token_hex(6),
) -> list[str]:
    """Issue `count` ids for one tester. Each id is reserved once with the private writer.

    An id is `f-<slug>-<random hex>`: it holds nothing derived from data. A name that is
    already reserved is skipped and a fresh token is drawn.
    """
    _check_slug(slug)
    issued = pass_dir / "issued"
    issued.mkdir(parents=True, exist_ok=True)
    ids: list[str] = []
    while len(ids) < count:
        candidate = f"{ID_PREFIX}{slug}-{token()}"
        try:
            writer(issued / candidate, b"")
        except FileExistsError:
            continue
        ids.append(candidate)
    return ids


def handback(pass_dir: Path, slug: str, *, exit_code: int) -> str:
    """One line: counts and ids. It reads file names only, never a record."""
    _check_slug(slug)
    prefix = f"{ID_PREFIX}{slug}-"
    issued = sorted(p.name for p in (pass_dir / "issued").glob(prefix + "*"))
    findings = pass_dir / "findings"
    written = [i for i in issued if (findings / f"{i}.toml").exists()]
    return (
        f"tester={slug} findings={len(written)} issued={len(issued)} "
        f"exit={exit_code} ids={','.join(written)}"
    )


def _run(argv: list[str]) -> int:
    return subprocess.run(argv, check=False).returncode


def launch(
    *,
    system: str,
    slug: str,
    agent_argv: Sequence[str],
    pass_dir: Path,
    id_count: int,
    findings_tool: str,
    writer: Writer | None = None,
    runner: Callable[[list[str]], int] = _run,
) -> str:
    """Issue ids, create the capture file, run the tester, return the hand-back line."""
    write = writer or _default_writer()
    ids = allocate_ids(pass_dir, slug, id_count, writer=write)
    capture_dir = pass_dir / "capture"
    capture_dir.mkdir(parents=True, exist_ok=True)
    capture = capture_dir / f"{slug}.log"
    write(capture, b"")
    argv = build_command(
        system=system,
        slug=slug,
        agent_argv=agent_argv,
        pass_dir=pass_dir,
        capture_path=capture,
        ids=ids,
        findings_tool=findings_tool,
    )
    return handback(pass_dir, slug, exit_code=runner(argv))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Start one QA tester (see docs/qa/beta-program.md)."
    )
    parser.add_argument("slug", help="tester slug, for example p1 or checklist")
    parser.add_argument("--pass-dir", type=Path, required=True)
    parser.add_argument("--ids", type=int, default=20, help="finding ids to issue")
    parser.add_argument("--findings-tool", default="/opt/decoy-qa/findings.py")
    parser.add_argument("agent", nargs=argparse.REMAINDER, help="agent command after --")
    args = parser.parse_args(argv)
    agent = args.agent[1:] if args.agent[:1] == ["--"] else args.agent
    if not agent:
        parser.error("give the agent command after --")
    system = "darwin" if sys.platform == "darwin" else "linux"
    try:
        line = launch(
            system=system,
            slug=args.slug,
            agent_argv=agent,
            pass_dir=args.pass_dir,
            id_count=args.ids,
            findings_tool=args.findings_tool,
        )
    except LaunchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
