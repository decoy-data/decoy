"""`decoy scan` internals: argument resolution, the engine call, the report and the diff rules.

Other packages import these names, never `decoy.cli.scanning._multi`, `._engine_call` or `._diff`.
"""

from decoy.cli.scanning._detectors import DETECTORS_OPTION, NER_MODEL_OPTION
from decoy.cli.scanning._diff import ScanDiff, diff_scan_sets, pii_bucket
from decoy.cli.scanning._engine_call import (
    DEFAULT_SCAN_ROWS,
    SampleStrategy,
    ScanRun,
    ScanUsageError,
    check_scan_options,
    core_bytes,
    scan_descriptors,
)
from decoy.cli.scanning._multi import (
    resolve_sources,
    run_scan,
    saved_field_facts,
    table_name_from_path,
)

__all__ = [
    "DEFAULT_SCAN_ROWS",
    "DETECTORS_OPTION",
    "NER_MODEL_OPTION",
    "SampleStrategy",
    "ScanDiff",
    "ScanRun",
    "ScanUsageError",
    "check_scan_options",
    "core_bytes",
    "diff_scan_sets",
    "pii_bucket",
    "resolve_sources",
    "run_scan",
    "saved_field_facts",
    "scan_descriptors",
    "table_name_from_path",
]
