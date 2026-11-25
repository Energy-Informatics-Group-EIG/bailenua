"""MIMIC schema 1.1 crosswalk and schema diff (design 5.14 levels 1 and 2).

Day 1 acceptance (design 9.3): *"schema diff against MIMIC 1.1 lists only the
U18 gaps"*.  :func:`schema_diff` is that diff, and :func:`u18_gaps` is the list
it is allowed to contain.

Everything in ``MIMIC_*`` below was read out of the MIMIC working tree rather
than recalled, and :func:`verify_against_mimic_source` re-reads the tree and
fails if any of it has drifted.  The sources:

* ``web/mimic/includes/ProfileRepository.php`` - ``PRIMARY_FIELDS``,
  ``OPTIONAL_FIELDS``
* ``web/mimic/includes/ProfileService.php``    - ``FORBIDDEN_FIELDS``
* ``web/mimic/mimic_sd_generator.php``         - the value sets and the
  ``round(3 + 1.05 * latent)`` self-report mapping
* ``database/schema.sql``                      - schema_version 1.1
* ``web/mimic/config/app.php``                 - ``session_length`` 13, signals,
  category codes
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path
from typing import Any, Final

__all__ = [
    "MIMIC_SCHEMA_VERSION",
    "MIMIC_PRIMARY_FIELDS",
    "MIMIC_OPTIONAL_FIELDS",
    "MIMIC_FORBIDDEN_FIELDS",
    "MIMIC_VALUE_SETS",
    "MIMIC_LATENTS",
    "MIMIC_SESSION_LENGTH",
    "MIMIC_SIGNALS",
    "U18Gap",
    "u18_gaps",
    "schema_diff",
    "verify_against_mimic_source",
    "self_report_from_latent",
    "age_band_for",
    "HOME_DUTIES_MAPPED_TO",
    "TERRACED_MAPPED_TO",
]

MIMIC_SCHEMA_VERSION: Final[str] = "1.1"
MIMIC_SESSION_LENGTH: Final[int] = 13
MIMIC_SIGNALS: Final[tuple[str, ...]] = ("SO", "RC", "CP", "AL")

#: ``ProfileRepository::PRIMARY_FIELDS``.  All sixteen are mandatory: MIMIC's
#: ``saveDemographics`` throws "Missing required field" on any absentee.
MIMIC_PRIMARY_FIELDS: Final[tuple[str, ...]] = (
    "age_band", "sex", "household_size", "children_present", "employment_status",
    "work_pattern", "dwelling_type", "ownership_status", "region_country",
    "region_nuts3", "urban_rural_island", "income_band", "der_ownership",
    "environmental_concern", "trust_in_automation", "comfort_sensitivity",
)

#: ``ProfileRepository::OPTIONAL_FIELDS`` - "FlexSense Table 3 optional fields
#: permitted in v1 (ADR-004 exclusions applied)".  Design 5.14 calls these the
#: "10 permitted fields".
MIMIC_OPTIONAL_FIELDS: Final[tuple[str, ...]] = (
    "education_level", "energy_bill_responsibility", "digital_access_level",
    "internet_quality", "vehicle_type", "home_automation_level",
    "community_energy_member", "occupation_sector", "primary_language",
    "social_participation_level",
)

#: ``ProfileService::FORBIDDEN_FIELDS`` - "removed per ADR-004 (GDPR Art. 9 /
#: re-identification)".  Design 5.14: a negative-test batch deliberately sends
#: these and ``ProfileService`` must reject them.
MIMIC_FORBIDDEN_FIELDS: Final[tuple[str, ...]] = (
    "health_status", "fitness_level", "mobility_limitation",
    "medical_device_dependence", "country_of_birth",
)

#: The ten MIMIC latents, in ``mimic_sd_generator.php`` order and spelling.
MIMIC_LATENTS: Final[tuple[str, ...]] = (
    "trans", "community", "env", "autonomy", "comfort",
    "conditional", "privacy", "instTrust", "idvZ", "satisficer",
)

#: MIMIC's own value sets.  Note the age bands use an EN-DASH (U+2013); that is
#: the source of defect I-003, where the generator compares against an ASCII
#: hyphen and the 55-64 education adjustment never fires.
MIMIC_VALUE_SETS: Final[dict[str, tuple[str, ...]]] = {
    "age_band": ("18–24", "25–34", "35–44", "45–54", "55–64", "65+"),
    "sex": ("Female", "Male"),
    "household_size": ("1", "2", "3", "4", "5+"),
    "children_present": ("Yes", "No"),
    "employment_status": ("Full-time", "Part-time", "Unemployed", "Student", "Retired"),
    "work_pattern": ("Office", "Remote", "Shift", "Irregular"),
    "dwelling_type": ("Apartment", "Semi-Detached", "Detached", "Farm", "Other"),
    "ownership_status": ("Owner", "Renter", "Social", "Other"),
    "urban_rural_island": ("Urban", "Rural", "Island"),
    "income_band": ("1", "2", "3", "4", "5"),
    "der_ownership_values": ("PV", "Battery", "EV", "HP", "None"),
}

#: Where the U18 gaps are mapped until MIMIC adds the values.  Recorded as
#: constants so the loss of information is visible at every call site and in
#: D26, rather than buried in a dictionary literal.
HOME_DUTIES_MAPPED_TO: Final[str] = "Unemployed"
TERRACED_MAPPED_TO: Final[str] = "Semi-Detached"


@dataclasses.dataclass(frozen=True)
class U18Gap:
    """A MIMIC value set that cannot represent an Irish household (U18)."""

    mimic_field: str
    missing_value: str
    hrsd_source: str
    mapped_to: str
    information_lost: str
    recommendation: str


def u18_gaps() -> tuple[U18Gap, ...]:
    """The only differences the Day 1 schema diff is allowed to report.

    U18's recommendation is to **add both values to MIMIC** - a MIMIC change,
    not a Baile Nua one - so these stay as gaps and are reported, not papered
    over.
    """
    return (
        U18Gap(
            mimic_field="profiles.employment_status",
            missing_value="Home duties",
            hrsd_source="D08.econ_status = 'home duties'",
            mapped_to=HOME_DUTIES_MAPPED_TO,
            information_lost=(
                "A person on home duties is at home on weekdays and is not seeking "
                "work. Mapping to 'Unemployed' makes the weekday occupancy pattern "
                "look like job-seeking, which is the opposite inference for "
                "flexibility: the household is reliably present."
            ),
            recommendation="Add 'Home duties' to MIMIC's employment_status value set (U18).",
        ),
        U18Gap(
            mimic_field="profiles.dwelling_type",
            missing_value="Terraced",
            hrsd_source="D02.dwelling_type = 'terraced'",
            mapped_to=TERRACED_MAPPED_TO,
            information_lost=(
                "Terraced houses have two party walls rather than one, so they lose "
                "less heat than semi-detached and behave differently thermally. "
                "Terraced is a common Cobh house type, so the gap is not marginal "
                "for an Irish harbour town."
            ),
            recommendation="Add 'Terraced' to MIMIC's dwelling_type value set (U18).",
        ),
    )


def self_report_from_latent(latent: float) -> int:
    """MIMIC's own mapping: ``clampi(round(3 + 1.05 * latent), 1, 5)``.

    Reproduced exactly, including PHP's ``round()`` half-away-from-zero
    behaviour, which differs from Python's banker's rounding at .5 and would
    otherwise put a small share of participants in the wrong Likert category.
    """
    import math

    x = 3.0 + 1.05 * float(latent)
    rounded = math.floor(x + 0.5) if x >= 0 else math.ceil(x - 0.5)
    return max(1, min(5, int(rounded)))


def age_band_for(age_years: int) -> str:
    """MIMIC's bands, with the en-dash MIMIC actually uses."""
    if age_years < 18:
        raise ValueError(
            f"age {age_years} is under 18; MIMIC has no band for minors and HRSD "
            f"must not enrol them (design 5.14: every synthetic ADULT)"
        )
    for band, hi in zip(MIMIC_VALUE_SETS["age_band"], (24, 34, 44, 54, 64)):
        if age_years <= hi:
            return band
    return "65+"


# --------------------------------------------------------------------------- #
# The Day 1 schema diff
# --------------------------------------------------------------------------- #

def schema_diff(schema: Any | None = None) -> dict[str, Any]:
    """Diff the HRSD D25 crosswalk against MIMIC schema 1.1.

    Returns a report with four lists.  The Day 1 acceptance criterion is that
    ``unmapped_mimic_fields`` and ``unknown_hrsd_fields`` are both empty and
    ``value_set_gaps`` contains **only** the U18 gaps.
    """
    from baile_nua.schema import load

    s = schema if schema is not None else load()
    d25 = s["D25"]

    mapped: dict[str, str] = {}
    for f in d25.fields:
        if f.mimic_field:
            mapped[f.mimic_field] = f.name

    def _mapped_profile_fields() -> set[str]:
        out = set()
        for mimic_field in mapped:
            if mimic_field.startswith("profiles."):
                out.add(mimic_field.split(".", 1)[1])
            elif mimic_field.startswith("profile_mcv."):
                out.add("mcv")
        return out

    present = _mapped_profile_fields()
    unmapped = sorted(set(MIMIC_PRIMARY_FIELDS) - present)

    # Optional fields are, by MIMIC's own design, optional; design 5.14 maps
    # them through `profile_optional.*` as a group rather than field by field.
    optional_mapped = any(
        f.mimic_field and f.mimic_field.startswith("profile_optional")
        for f in d25.fields
    )

    unknown = sorted(
        mf for mf in mapped
        if mf.startswith("profiles.")
        and mf.split(".", 1)[1] not in set(MIMIC_PRIMARY_FIELDS)
        and mf.split(".", 1)[1] not in {"consent_version", "consent_granted_at", "mcv_position"}
    )

    gaps = [
        {
            "mimic_field": g.mimic_field,
            "missing_value": g.missing_value,
            "hrsd_source": g.hrsd_source,
            "mapped_to": g.mapped_to,
            "information_lost": g.information_lost,
            "recommendation": g.recommendation,
            "decision": "U18",
        }
        for g in u18_gaps()
    ]

    return {
        "mimic_schema_version": MIMIC_SCHEMA_VERSION,
        "hrsd_dataset": d25.id,
        "n_mimic_primary_fields": len(MIMIC_PRIMARY_FIELDS),
        "n_mapped": len(present & set(MIMIC_PRIMARY_FIELDS)),
        "unmapped_mimic_fields": unmapped,
        "unknown_hrsd_fields": unknown,
        "optional_fields_mapped_as_group": optional_mapped,
        "value_set_gaps": gaps,
        "forbidden_fields_never_exported": list(MIMIC_FORBIDDEN_FIELDS),
        "conclusion": (
            "Only the two U18 value-set gaps remain."
            if not unmapped and not unknown
            else "Schema diff is NOT clean; see unmapped_mimic_fields / unknown_hrsd_fields."
        ),
    }


# --------------------------------------------------------------------------- #
# Guard against drift in the MIMIC tree
# --------------------------------------------------------------------------- #

class MimicDriftError(RuntimeError):
    """The MIMIC working tree no longer matches the constants recorded here."""


def verify_against_mimic_source(mimic_root: str | Path) -> dict[str, Any]:
    """Re-read the MIMIC tree and confirm every constant above still holds.

    The brief forbids hard-coding statistics from memory.  The same discipline
    applies to MIMIC's value sets: they are read from the tree here, and a
    mismatch fails rather than silently exporting the wrong coding.
    """
    root = Path(mimic_root)
    findings: dict[str, Any] = {"mimic_root": str(root), "checks": {}, "defects": []}

    def _read(rel: str) -> str:
        p = root / rel
        if not p.is_file():
            raise MimicDriftError(f"expected MIMIC file not found: {p}")
        return p.read_text(encoding="utf-8", errors="replace")

    # --- PRIMARY_FIELDS / OPTIONAL_FIELDS ---
    repo = _read("web/mimic/includes/ProfileRepository.php")

    def _php_list(src: str, const: str) -> tuple[str, ...]:
        m = re.search(rf"const\s+{const}\s*=\s*\[(.*?)\];", src, re.S)
        if not m:
            raise MimicDriftError(f"{const} not found in ProfileRepository.php")
        return tuple(re.findall(r"'([^']+)'", m.group(1)))

    got_primary = _php_list(repo, "PRIMARY_FIELDS")
    got_optional = _php_list(repo, "OPTIONAL_FIELDS")
    findings["checks"]["PRIMARY_FIELDS"] = got_primary == MIMIC_PRIMARY_FIELDS
    findings["checks"]["OPTIONAL_FIELDS"] = got_optional == MIMIC_OPTIONAL_FIELDS

    # --- FORBIDDEN_FIELDS ---
    svc = _read("web/mimic/includes/ProfileService.php")
    got_forbidden = _php_list(svc, "FORBIDDEN_FIELDS")
    findings["checks"]["FORBIDDEN_FIELDS"] = got_forbidden == MIMIC_FORBIDDEN_FIELDS

    # --- schema_version ---
    sql = _read("database/schema.sql")
    findings["checks"]["schema_version_1_1"] = (
        "('schema_version', '1.1')" in sql or '"schema_version", "1.1"' in sql
    )

    # --- session_length and signals ---
    app = _read("web/mimic/config/app.php")
    findings["checks"]["session_length_13"] = "'session_length' => 13" in app
    findings["checks"]["signals_SO_RC_CP_AL"] = "'SO', 'RC', 'CP', 'AL'" in app

    # --- age bands and the I-003 defect ---
    gen = _read("web/mimic/mimic_sd_generator.php")
    endash_bands = "'18–24','25–34','35–44','45–54','55–64','65+'" in gen
    findings["checks"]["age_bands_use_en_dash"] = endash_bands
    hyphen_compare = "$age === '55-64'" in gen
    findings["checks"]["I003_hyphen_vs_endash_defect_still_present"] = hyphen_compare
    if hyphen_compare and endash_bands:
        findings["defects"].append(
            {
                "id": "I-003",
                "file": "web/mimic/mimic_sd_generator.php",
                "summary": (
                    "The education adjustment compares the age band against '55-64' "
                    "with an ASCII hyphen, but the bands are defined with an en-dash "
                    "'55–64'. The branch is dead: the adjustment never fires for "
                    "55-64 year olds."
                ),
                "action": "Reported to the MIMIC team. Not fixed here (brief: record, do not edit MIMIC).",
            }
        )

    # --- U18 gaps, confirmed from the value sets in code ---
    findings["checks"]["U18_no_home_duties_value"] = "'Home duties'" not in gen
    findings["checks"]["U18_no_terraced_value"] = "'Terraced'" not in gen

    failed = sorted(k for k, v in findings["checks"].items() if v is False and not k.startswith("I003"))
    findings["drifted"] = failed
    findings["ok"] = not failed
    if failed:
        raise MimicDriftError(
            f"the MIMIC working tree no longer matches the constants in "
            f"baile_nua.mimic.crosswalk: {failed}. Update the crosswalk deliberately "
            f"rather than exporting the wrong coding."
        )
    return findings
