"""`decoy report vault`: the authenticated header and counts of a `decoy run --vault` file.

Split out of `report.py`, which is over the module-size cap and may only shrink. The command opens
the vault through the engine's `open_vault`, which authenticates the header and every segment and
returns the header from the same read, so what is shown is what was proven.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer

from decoy import _mask_secret
from decoy._config_file import ConfigFileError, config_refusal, load_config_mapping
from decoy.cli.exit_codes import EXIT_USAGE, exit_code_for
from decoy.cli.io import pipeline_option, resolve_pipeline
from decoy.cli.reports._refusal import vault_hint
from decoy.ui.output import OutputMode, OutputState, emit_error, emit_json, setup_output
from decoy.ui.theme import code, hint, success

if TYPE_CHECKING:
    from decoy_engine.vault import OpenedVault

# Hex characters of the vault id shown. The key check value is never shown.
_VAULT_ID_SHOWN = 12

VAULT_EPILOG = """\
Examples:

  decoy report vault vault.bin --config pipeline.yaml
    Show format, key version, a short vault id, entry count, namespaces, and
    ambiguous-dropped count.

  decoy report vault vault.bin --config pipeline.yaml --json
    Same data as a JSON envelope for scripting.

  decoy report vault vault.bin --config pipeline.yaml --quiet
    Silent mode; exit code 0 = vault opened successfully.

The vault opens only under the mask secret that the `decoy run --vault`
call used. Pass the same secret with --mask-secret, or name it in the
config's global_settings.mask_secret_ref. The seed is not key material.
A missing or wrong secret exits 1. A vault that fails its own
authentication (edited, reordered or spliced) exits 3 with
`vault_tampered`. The report never prints values or the key check value.

See also: decoy run --vault, decoy unmask --vault.
"""


def vault_command(
    vault: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        help="The vault file written by `decoy run --vault`.",
    ),
    config: str = pipeline_option(
        ...,
        "--config",
        help=(
            "The pipeline file (.yaml or .decoy) the mask run used. The vault opens only under "
            "the mask secret that run used (--mask-secret or global_settings.mask_secret_ref)."
        ),
    ),
    mask_secret: str | None = typer.Option(None, "--mask-secret", help=_mask_secret.FLAG_HELP),
    json_: bool = typer.Option(
        False,
        "--json",
        help="Emit a structured JSON result on stdout. Errors still go to stderr.",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress stdout. Errors still go to stderr; exit code carries the result.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable debug-level CLI logs on stderr.",
    ),
) -> None:
    """Inspect a vault file: report entry count, namespaces, and dropped-ambiguous count.

    Also shows the vault format, the key version and a short vault id from its authenticated
    header.

    Opens the vault with the mask secret that --mask-secret or
    global_settings.mask_secret_ref in the pipeline config names, the secret the `decoy run --vault` call
    used; the seed is not key material. A missing or wrong secret exits 1.
    Exits 0 on success, 1 on a config/vault/usage error, 3 on a vault that fails its
    own authentication (vault_tampered).
    """
    state = setup_output(json_, quiet, verbose)
    config_path = resolve_pipeline(config, state, "report vault").yaml

    def _emit_error(message: str, *, hint_text: str | None = None, code: str | None = None) -> None:
        emit_error(
            state, "report vault", message, code=code, hint=hint_text, context={"vault": str(vault)}
        )

    try:
        raw = load_config_mapping(config_path)
    except (ConfigFileError, OSError) as exc:
        _emit_error(**config_refusal(exc))
        raise typer.Exit(code=exit_code_for(exc))
    try:
        _mask_secret.apply_mask_secret(raw, mask_secret)
    except _mask_secret.MaskSecretFlagError as exc:
        _emit_error(str(exc))
        raise typer.Exit(code=EXIT_USAGE)

    from decoy_engine import VaultError
    from decoy_engine.keyprovider import MaskSecretError

    from decoy import _mask_secret_guidance

    try:
        opened = _open(raw, vault)
    except _NoSecretError:
        # A vault is always keyed; there is no seed fallback to open it with.
        _emit_error(_mask_secret_guidance.REPORT_VAULT)
        raise typer.Exit(code=EXIT_USAGE)
    except MaskSecretError as exc:
        _emit_error(
            _mask_secret_guidance.secret_error_text(exc, _mask_secret_guidance.REPORT_VAULT)
        )
        raise typer.Exit(code=EXIT_USAGE)
    except VaultError as refusal:
        _emit_error(refusal.message, hint_text=vault_hint(refusal.code), code=refusal.code)
        raise typer.Exit(code=exit_code_for(refusal))
    _show(state, vault, opened)


class _NoSecretError(Exception):
    """The config admits no secret, so there is nothing to open the vault with."""


def _open(raw: dict[str, object], vault: Path) -> OpenedVault:
    """Open the vault under the config's admitted secret; the scope closes it on every exit.

    `open_vault` authenticates the header and every segment, and returns the header from the
    same read. The admission is the one `decoy unmask` reaches through `unmask_pipeline`."""
    from decoy_engine.vault import open_vault

    with _mask_secret.admitted_prepared_secret(raw) as prepared:
        if prepared is None:
            raise _NoSecretError
        return open_vault(str(vault), prepared)


def _show(state: OutputState, vault: Path, opened: OpenedVault) -> None:
    """Print the header fields and counts; never an entry or the key check value."""
    from decoy_engine.vault import VAULT_FORMAT_VERSION

    header = opened.header
    namespaces = sorted({ns for (ns, _) in opened.mapping})
    vault_id = header.vault_id[:_VAULT_ID_SHOWN]
    if state.mode is OutputMode.json:
        emit_json(
            state,
            {
                "command": "report vault",
                "status": "ok",
                "vault": str(vault),
                "format": header.format,
                "key_version": header.key_version,
                "vault_id": vault_id,
                "authenticated": header.format == VAULT_FORMAT_VERSION,
                "entries": header.entry_count,
                "namespaces": namespaces,
                "ambiguous_dropped": opened.ambiguous_dropped,
            },
        )
        return
    if state.mode is OutputMode.quiet:
        return
    state.console.print(success("OK"), code(str(vault)))
    state.console.print(f"  format:            {header.format}")
    state.console.print(f"  key version:       {header.key_version}")
    state.console.print(f"  vault id:          {vault_id}")
    state.console.print(f"  entries:           {header.entry_count}")
    state.console.print(f"  namespaces ({len(namespaces)}):   {', '.join(namespaces) or '(none)'}")
    state.console.print(f"  ambiguous dropped: {opened.ambiguous_dropped}")
    if header.format != VAULT_FORMAT_VERSION:
        # An older vault opens read-only and its header is not authenticated.
        state.console.print(
            " ",
            hint("hint:"),
            f"this vault is {header.format}, which the engine only reads, and its header is not "
            "authenticated; re-mask with `decoy run --vault` to get an authenticated vault.",
        )
