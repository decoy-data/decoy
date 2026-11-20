"""`decoy scan` internals: argument resolution, the engine call, the report and the diff rules.

Other packages import these names, never `decoy.cli.scanning._multi` or `._diff`.
"""

from decoy.cli.scanning._diff import ScanDiff, diff_scan_sets, pii_bucket
from decoy.cli.scanning._multi import (
    ScanUsageError,
    run_scan,
    saved_field_facts,
    table_name_from_path,
)

__all__ = [
    "ScanDiff",
    "ScanUsageError",
    "diff_scan_sets",
    "pii_bucket",
    "run_scan",
    "saved_field_facts",
    "table_name_from_path",
]
