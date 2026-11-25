"""Tests for the U28 release policy and its storage projection.

The projection decides whether the full ten-year town run happens at all
(U28 clause 4), so it has to reproduce its own basis before any confidence is
placed in a configuration nobody has run.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from baile_nua.observation.sensors import TIER_DEVICES
from baile_nua.population.buildings import SENSOR_TIER_UPTAKE
from baile_nua.release.policy import (
    MATERIALISATION_POLICY,
    project_package,
    write_projection,
)

ROOT = Path(__file__).resolve().parents[2]


def _measured() -> tuple[dict, dict, float, int]:
    diag = json.loads((ROOT / "v1" / "run_diagnostics.json").read_text())
    measured = diag["benchmark"]["storage"]["by_dataset"]
    estate_mix = {k: float(v) for k, v in diag["slice"]["sensor_tiers"].items()}
    channels = {k: len(v) for k, v in TIER_DEVICES.items()}
    estate_channels = sum(
        estate_mix.get(t, 0) * channels.get(t, 0) for t in channels
    )
    n_town = int(diag["benchmark"]["full_town_projection"]["n_town_homes"])
    return measured, estate_mix, estate_channels, n_town


def test_the_projection_reproduces_the_measurement_it_scales():
    """The self-check. A projection that cannot reproduce its own basis is a guess.

    This is what caught the bug: the sub-metered cohort is a fixed town-level
    set of 20 to 50 homes at tier T4 (6.4 item 6), and applying it as a share
    of whatever slice was being projected made a 50-home estate 70%
    sub-metered - so the U28 estate came out LARGER than the pre-U28 one.
    """
    measured, estate_mix, estate_channels, _n = _measured()
    diag = json.loads((ROOT / "v1" / "run_diagnostics.json").read_text())
    measured_gb = diag["benchmark"]["storage"]["total_bytes"] / 1024**3

    proj = project_package(
        measured=measured, n_homes=50, n_years=1, tier_mix=estate_mix,
        channels_per_tier={k: len(v) for k, v in TIER_DEVICES.items()},
        estate_channels=estate_channels, n_sub_metered_town=0,
        apply_u28=False,
    )
    assert abs(proj.total_gb - measured_gb) / measured_gb < 0.02, (
        f"the projection gives {proj.total_gb:.3f} GB for the configuration "
        f"that was actually measured at {measured_gb:.3f} GB"
    )


def test_u28_makes_every_configuration_smaller_not_larger():
    """The direction of the ruling, asserted on every scale it is applied at."""
    measured, estate_mix, estate_channels, n_town = _measured()
    channels = {k: len(v) for k, v in TIER_DEVICES.items()}
    for homes, years, mix, n_sub in (
        (50, 1, estate_mix, 0),
        (50, 10, estate_mix, 0),
        (n_town, 1, SENSOR_TIER_UPTAKE, 35),
        (n_town, 10, SENSOR_TIER_UPTAKE, 35),
    ):
        kw = dict(
            measured=measured, n_homes=homes, n_years=years, tier_mix=mix,
            channels_per_tier=channels, estate_channels=estate_channels,
            n_sub_metered_town=n_sub, n_town_homes=n_town,
        )
        before = project_package(**kw, apply_u28=False).total_gb
        after = project_package(**kw, apply_u28=True).total_gb
        assert after < before, (
            f"{homes} homes x {years} years: U28 gives {after:.2f} GB against "
            f"{before:.2f} GB before the ruling. Rendering on demand cannot "
            f"make a package bigger."
        )


def test_the_privacy_relevant_views_are_kept_in_full():
    """U28 clause 3. The 7.8 inference tests must still have something to attack.

    A package that shrank by dropping the export views would put the privacy
    question out of reach, which is the opposite of what a storage ruling
    should do.
    """
    assert MATERIALISATION_POLICY["D19"]["materialised"] is True
    assert MATERIALISATION_POLICY["D19"]["homes"] == "all"
    assert "7.8" in MATERIALISATION_POLICY["D19"]["why"]
    assert MATERIALISATION_POLICY["D18_meter"]["homes"] == "all"
    assert "30 minute" in MATERIALISATION_POLICY["D18_meter"]["interval"].replace(
        "30 minutes", "30 minute"
    )

    measured, estate_mix, estate_channels, n_town = _measured()
    proj = project_package(
        measured=measured, n_homes=n_town, n_years=10,
        tier_mix=SENSOR_TIER_UPTAKE,
        channels_per_tier={k: len(v) for k, v in TIER_DEVICES.items()},
        estate_channels=estate_channels, n_sub_metered_town=35,
        n_town_homes=n_town, apply_u28=True,
    )
    # Every home must have a 30-minute meter series: two channels, 48 a day.
    expected = n_town * 2 * 48 * 365 * 10
    assert proj.by_dataset["D18_meter"]["rows"] == expected


def test_the_events_are_never_dropped():
    """D13 is what everything else is rendered FROM (R13)."""
    assert MATERIALISATION_POLICY["D13"]["materialised"] is True
    assert MATERIALISATION_POLICY["D13"]["homes"] == "all"
    measured, estate_mix, estate_channels, n_town = _measured()
    channels = {k: len(v) for k, v in TIER_DEVICES.items()}
    kw = dict(
        measured=measured, n_homes=n_town, n_years=10,
        tier_mix=SENSOR_TIER_UPTAKE, channels_per_tier=channels,
        estate_channels=estate_channels, n_sub_metered_town=35,
        n_town_homes=n_town,
    )
    before = project_package(**kw, apply_u28=False)
    after = project_package(**kw, apply_u28=True)
    assert before.by_dataset["D13"]["rows"] == after.by_dataset["D13"]["rows"], (
        "the event log must be identical under either policy; if it shrank, "
        "something that cannot be re-rendered has been thrown away"
    )


def test_the_written_projection_states_a_decision_either_way():
    """The artefact must say proceed or stop, and the figure behind it."""
    out = write_projection(out_path=Path("/tmp/bn_projection_test.json"))
    v = out["verdict"]
    assert v["decision"].startswith(("PROCEED", "STOP"))
    assert isinstance(v["fits"], bool)
    assert v["ten_year_town_gb_with_margin_after"] > 0
    assert v["margin"] == 1.5
    # The reduction must be real and reported.
    assert v["reduction_factor"] > 1.5, (
        f"U28 only reduced the package by {v['reduction_factor']}x; the "
        f"ruling's point was to make the ten-year run feasible"
    )
    assert out["what_is_given_up"], (
        "the policy must state what a consumer loses, not only what is saved"
    )


# --------------------------------------------------------------------------- #
# the storage fallback (U28 amendment, 9 October)
# --------------------------------------------------------------------------- #

def test_the_storage_fallback_is_smaller_than_the_ruled_policy():
    measured, estate_mix, estate_channels, n_town = _measured()
    channels = {k: len(v) for k, v in TIER_DEVICES.items()}
    kw = dict(
        measured=measured, n_homes=n_town, n_years=10,
        tier_mix=SENSOR_TIER_UPTAKE, channels_per_tier=channels,
        estate_channels=estate_channels, n_sub_metered_town=35,
        n_town_homes=n_town, apply_u28=True,
    )
    ruled = project_package(**kw, storage_fallback=False)
    fallback = project_package(**kw, storage_fallback=True)
    assert fallback.total_gb < ruled.total_gb
    # The saving must come from D18, not from quietly dropping something else.
    assert fallback.by_dataset["D19"]["rows"] == ruled.by_dataset["D19"]["rows"]
    assert fallback.by_dataset["D13"]["rows"] == ruled.by_dataset["D13"]["rows"]
    assert (
        fallback.by_dataset["D18_meter"]["rows"]
        == ruled.by_dataset["D18_meter"]["rows"]
    ), "every home keeps its 30-minute meter under either policy"
    assert (
        fallback.by_dataset["D18_sensored"]["rows"]
        < ruled.by_dataset["D18_sensored"]["rows"]
    )


def test_the_fallback_keeps_the_sub_metered_subset_at_one_minute():
    """6.4 item 6 is the part whose VALUE a render cannot reconstruct.

    The sub-metered subset's worth is its installer log, its labels and its
    mislabelled and failed channels - not the series, which renders like any
    other. That is why it is the one cohort the fallback still materialises.
    """
    measured, estate_mix, estate_channels, n_town = _measured()
    channels = {k: len(v) for k, v in TIER_DEVICES.items()}
    n_sub = 35
    fallback = project_package(
        measured=measured, n_homes=n_town, n_years=10,
        tier_mix=SENSOR_TIER_UPTAKE, channels_per_tier=channels,
        estate_channels=estate_channels, n_sub_metered_town=n_sub,
        n_town_homes=n_town, apply_u28=True, storage_fallback=True,
    )
    note = fallback.by_dataset["D18_sensored"]["note"]
    assert "FALLBACK" in note and "sub-metered" in note
    assert fallback.by_dataset["D18_sensored"]["rows"] > 0, (
        "the fallback must still materialise the labelled subset"
    )


def test_the_policy_choice_never_trusts_a_volume_s_own_claim():
    """I-036's trap, asserted on the real machine state.

    /Volumes/Vault claims Device Location External and Removable Media
    Removable and is a sparse bundle on the internal disk. The detector must
    reject it on protocol and backing file, and must say so.
    """
    from baile_nua.release.storage import find_external_drive, inspect_volume

    chosen, candidates = find_external_drive()
    for cand in candidates:
        if cand["is_disk_image"]:
            assert cand["usable_as_external"] is False, (
                f"{cand['mount_point']} is a disk image and was accepted as "
                f"an external drive"
            )
            assert cand["backing_file"], "a rejected image must name its backing file"
            assert "disk image" in cand["reason"].lower()
    if chosen is not None:
        assert not chosen.is_disk_image
        assert chosen.claims_external


def test_a_disk_image_backed_on_the_internal_disk_is_detected_as_such():
    """The st_dev comparison that looked right and was wrong.

    On APFS the boot volume and the Data volume have different device ids while
    sharing one physical disk, so comparing st_dev against "/" reports a
    backing file in /Users as not-internal. The check resolves the backing
    file to its mount point instead.
    """
    from baile_nua.release.storage import _mount_point_of, inspect_volume
    from pathlib import Path as _P

    facts = inspect_volume("/Volumes/Vault")
    if not facts.exists or not facts.is_disk_image:
        pytest.skip("no disk-image volume mounted to check against")
    assert facts.backing_file
    assert facts.backing_on_internal is True, (
        f"backing file {facts.backing_file} resolves to mount point "
        f"{_mount_point_of(facts.backing_file)} and was not recognised as "
        f"internal"
    )
