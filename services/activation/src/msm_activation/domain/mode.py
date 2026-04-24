from __future__ import annotations
from enum import Enum


class ActivationMode(str, Enum):
    """PRD §2.1 activation options."""
    DIRECT_OCI = "direct_oci"           # Option A
    SSGTM_PHOEBE = "ssgtm_phoebe"       # Option B (recommended, ADR 0001)
    HYBRID = "hybrid"                   # Option C — OCI while SSGTM stands up
