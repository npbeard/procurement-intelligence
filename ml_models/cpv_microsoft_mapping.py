"""
CPV → Microsoft Product Line Mapping

Maps EU CPV procurement codes to Microsoft's main product lines:
Azure, M365, Security, Dynamics, General IT.

Used to compute how relevant a tender is to Microsoft's portfolio
and to score buyer affinity.
"""

from __future__ import annotations

# Maps CPV group (first 3 digits of CPV code) to (product_line, relevance_score)
# relevance_score: 1.0 = core Microsoft product area, 0.5 = adjacent, 0.3 = generic IT
CPV_GROUP_MAP: dict[str, tuple[str, float]] = {
    # ── 48xxx Software packages ────────────────────────────────────────────────
    "480": ("General IT",  0.5),  # General software packages
    "481": ("Dynamics",    0.9),  # Business / ERP / accounting / CRM software
    "482": ("Azure",       1.0),  # Network, database, data processing software
    "483": ("Azure",       1.0),  # Database and data management software
    "484": ("M365",        1.0),  # Office automation and productivity software
    "485": ("M365",        0.9),  # Communications and collaboration software
    "486": ("Security",    1.0),  # Security, antivirus, identity software
    "487": ("General IT",  0.5),  # Development tools
    "488": ("General IT",  0.3),  # Educational / entertainment software
    "489": ("General IT",  0.4),  # Miscellaneous software

    # ── 72xxx IT Services ─────────────────────────────────────────────────────
    "720": ("General IT",  0.6),  # IT consultancy and advisory
    "721": ("Azure",       0.9),  # Internet, hosting, and cloud infrastructure
    "722": ("Azure",       1.0),  # Software development and cloud platforms
    "723": ("Azure",       0.9),  # Data processing and analytics services
    "724": ("Azure",       0.8),  # Database and data management services
    "725": ("Security",    1.0),  # IT security and cybersecurity services
    "726": ("M365",        0.9),  # Managed desktop, support, helpdesk services
    "727": ("Dynamics",    0.8),  # Business application and ERP services
    "728": ("General IT",  0.5),  # Other IT services
}

# Fallback for unknown CPV groups
_DEFAULT = ("General IT", 0.3)

# Human-readable product line descriptions for the dashboard
PRODUCT_LINE_DESCRIPTIONS = {
    "Azure":      "Azure — Cloud, Data, Infrastructure",
    "M365":       "M365 — Productivity & Collaboration",
    "Security":   "Security — Cybersecurity & Identity",
    "Dynamics":   "Dynamics — ERP, CRM & Business Apps",
    "General IT": "General IT",
}

ALL_PRODUCT_LINES = list(PRODUCT_LINE_DESCRIPTIONS.keys())


def get_cpv_mapping(cpv_code: str) -> tuple[str, float]:
    """Return (product_line, relevance_score) for a CPV code string."""
    group = str(cpv_code).strip()[:3]
    return CPV_GROUP_MAP.get(group, _DEFAULT)


def get_cpv_product_line(cpv_code: str) -> str:
    return get_cpv_mapping(cpv_code)[0]


def get_cpv_relevance(cpv_code: str) -> float:
    return get_cpv_mapping(cpv_code)[1]
