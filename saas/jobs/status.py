"""Live status extraction: log parsing, stage inference, noise filtering."""
from __future__ import annotations

import re


def _infer_pipeline_stage(log_lines: list[str]) -> int | None:
    """Map worker log lines to a pipeline stage number (1-5).

    Checked from latest phase to earliest so later markers that linger in
    log_text outrank earlier ones.

    Phase mapping (frontend STAGE_NAMES aligned):
      1 Seeding           = 'Generating ontology'
      2 Researching       = 'Building'
      3 Simulating        = 'Running simulation' / 'round='
      4 Analyzing         = 'preparing' (post-sim artifact extraction)
      5 Generating report = 'report'
    """
    log_text = " ".join(log_lines)
    if "report" in log_text.lower():
        return 5
    if "preparing" in log_text:
        return 4
    if "Running simulation" in log_text or "round=" in log_text:
        return 3
    if "Building" in log_text:
        return 2
    if "Generating ontology" in log_text:
        return 1
    return None


_LOG_NOISE_RE = re.compile(r'(GET /|POST /|HEAD /|OPTIONS /)')


def _extract_live_status(log_lines: list[str], max_rounds: int | None = None) -> dict:
    """Extract round count and cleaned log lines from pod pipeline log output.

    Returns a dict suitable for storing in the live_status JSONB column.
    Keys present: log_lines (always), round (if found), max_rounds (if provided).
    """
    cleaned = [
        line for line in log_lines
        if line.strip()
        and not _LOG_NOISE_RE.search(line)
        and len(line.strip()) >= 10
    ][-3:]

    round_num: int | None = None
    for line in log_lines:
        m = re.search(r'\bround[=\s]+(\d+)', line, re.IGNORECASE)
        if m:
            candidate = int(m.group(1))
            if round_num is None or candidate > round_num:
                round_num = candidate

    result: dict = {"log_lines": cleaned}
    if round_num is not None:
        result["round"] = round_num
    if max_rounds is not None:
        result["max_rounds"] = max_rounds
    return result
