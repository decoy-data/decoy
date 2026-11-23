"""`decoy report` subcommands that live outside `report.py`, which is over the module-size cap.

Other packages import these names, never `decoy.cli.reports._vault`.
"""

from decoy.cli.reports._refusal import is_vault_code, vault_hint
from decoy.cli.reports._vault import VAULT_EPILOG, vault_command

__all__ = ["VAULT_EPILOG", "is_vault_code", "vault_command", "vault_hint"]
