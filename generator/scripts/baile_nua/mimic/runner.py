"""The HRSD runner: synthetic participants through MIMIC's PUBLIC API (5.14 level 3).

Design 5.14 level 3, binding:

    Synthetic participants go through MIMIC's **public API**
    (``api/session.php``, ``api/response.php``, ``api/consent.php``), not
    straight into the database.  This exercises: session composition (11
    balanced items, 1 random item and 1 probe repeat), the randomised MCV
    position (pre or post), option-order randomisation, validation and rate
    limiting.

    The HRSD runner sees only the presented scenario and its displayed order,
    and answers with the HRSD willingness model applied to the four signals,
    **never to screen position** (position bias is planted only in test mode
    T10), response latency, and realistic abandonment.

So the runner behaves like a browser: one cookie jar per participant (MIMIC puts
the participant id in the PHP session), a CSRF token read from the page the way
the front end reads it, and the journey walked in MIMIC's own order as
``JourneyService`` defines it:

    consent -> profile -> [MCV if position is 'pre'] -> session -> N responses
            -> [MCV if position is 'post']

Two things the runner deliberately does **not** do:

* it never writes to the database directly, so MIMIC's validation, journey
  routing and rate limiting are all exercised;
* it never reads the option order and then answers by position.  The willingness
  model is given the four signals and the context, and the display position is
  looked up *afterwards* only to report what position the chosen signal happened
  to occupy - which is what T10 needs in order to detect a bias that is not
  there.

Safety: :func:`run_batch` calls ``provision.assert_local_only`` and the G-B
frozen-specification check before issuing a single request.
"""

from __future__ import annotations

import concurrent.futures as cf
import dataclasses
import re
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np
import requests

from baile_nua.mimic import crosswalk
from baile_nua.mimic import willingness as wg
from baile_nua.mimic.counters import MimicCounters
from baile_nua.mimic.extended_pool import PoolPerson
from baile_nua.mimic.provision import LOCAL_BASE_URL, assert_local_only
from baile_nua.rng import SeedTree, Stream

__all__ = [
    "ParticipantResult",
    "BatchResult",
    "MimicRunner",
    "CONSENT_VERSION_TEMPLATE",
    "FORBIDDEN_FIELD_PROBE",
]

#: Design 5.14 / U17: the marker MIMIC's own purge (``LIKE 'SYNTHETIC%'``) and
#: synthetic banner already understand, plus the pool code U17 asked for.
CONSENT_VERSION_TEMPLATE = "SYNTHETIC-HRSD-v1-{pool}"

#: The forbidden-field negative batch (design 5.14): "A negative-test batch
#: deliberately sends them and must be rejected by ``ProfileService``."
FORBIDDEN_FIELD_PROBE: dict[str, Any] = {
    "health_status": "Good",
    "fitness_level": "Moderate",
    "mobility_limitation": "None",
    "medical_device_dependence": "No",
    "country_of_birth": "IE",
}

_CSRF_RE = re.compile(r"window\.MIMIC\s*=\s*\{\s*csrf:\s*\"([0-9a-f]+)\"")


@dataclasses.dataclass
class ParticipantResult:
    pool_person_id: str
    #: The RESPONDENT this record belongs to: the linked population
    #: ``person_id`` for a panel wave, otherwise the pool person's own id.
    #:
    #: The two differ only for the linked panel, where one person answers 8 to
    #: 15 waves (I-075) and MIMIC's public API makes each wave a separate
    #: participant record (I-087).  The five 5.14 counters count respondents,
    #: because the E1 report's own rule is that "repeated sessions never count
    #: as unique participants".
    respondent_id: str = ""
    #: U19: the API timestamps are run time; this is the simulated date.
    simulated_session_date: str | None = None
    wave: int | None = None
    n_waves: int | None = None
    participant_id: str | None = None
    consent_version: str = ""
    mcv_position: str | None = None
    session_id: str | None = None
    n_responses: int = 0
    completed: bool = False
    abandoned: bool = False
    responses: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    errors: list[str] = dataclasses.field(default_factory=list)
    elapsed_s: float = 0.0
    #: D26 answer key for this participant.
    answer_key: dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class BatchResult:
    counters: MimicCounters
    participants: list[ParticipantResult]
    errors: list[str]
    elapsed_s: float
    config: dict[str, Any]

    @property
    def n_ok(self) -> int:
        return sum(1 for p in self.participants if p.participant_id)

    def summary(self) -> dict[str, Any]:
        err_kinds: dict[str, int] = {}
        for p in self.participants:
            for e in p.errors:
                kind = e.split(":", 1)[0][:48]
                err_kinds[kind] = err_kinds.get(kind, 0) + 1
        return {
            "counters": self.counters.as_dict(),
            "participants_created": self.n_ok,
            "participants_attempted": len(self.participants),
            "elapsed_s": round(self.elapsed_s, 1),
            "participants_per_second": round(self.n_ok / max(self.elapsed_s, 1e-9), 1),
            "error_kinds": err_kinds,
            "config": self.config,
        }


class MimicRunner:
    """Drives synthetic participants through the local MIMIC public API."""

    def __init__(
        self,
        *,
        base_url: str = LOCAL_BASE_URL,
        sandbox: Path | None = None,
        master_seed: int = 20261008,
        timeout: int = 60,
        max_retries: int = 3,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.sandbox = Path(sandbox) if sandbox else None
        self.tree = SeedTree(master_seed)
        self.timeout = timeout
        self.max_retries = max_retries
        self._lock = threading.Lock()
        self._seen_participants: set[str] = set()

    # -- low-level HTTP ------------------------------------------------------

    def _new_session(self) -> tuple[requests.Session, str]:
        """A fresh PHP session with its CSRF token, as a browser would get one.

        The token is published by ``includes/layout.php`` as
        ``window.MIMIC = { csrf: "..." }`` on any page that uses the layout, so
        reading it from ``register.php`` is the same thing the front end does.
        """
        s = requests.Session()
        s.headers.update({"User-Agent": "baile-nua-hrsd-runner/0.1 (local sandbox)"})
        r = s.get(f"{self.base_url}/register.php", timeout=self.timeout)
        r.raise_for_status()
        m = _CSRF_RE.search(r.text)
        if not m:
            raise RuntimeError(
                "could not read the CSRF token from register.php; MIMIC publishes "
                "it as window.MIMIC = { csrf: \"...\" } in includes/layout.php"
            )
        return s, m.group(1)

    def _post(self, s: requests.Session, path: str, body: dict[str, Any]) -> dict[str, Any]:
        last: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                r = s.post(f"{self.base_url}/{path}", json=body, timeout=self.timeout)
                try:
                    doc = r.json()
                except ValueError:
                    doc = {"ok": False, "error": {"code": "NON_JSON", "message": r.text[:200]}}
                doc["_http_status"] = r.status_code
                if r.status_code == 429:
                    # Should not happen under the U19 test-mode allowance; if it
                    # does, back off rather than losing the participant.
                    time.sleep(1.5 * (attempt + 1))
                    last = RuntimeError("RATE_LIMIT")
                    continue
                return doc
            except requests.RequestException as exc:
                last = exc
                time.sleep(0.4 * (attempt + 1))
        raise RuntimeError(f"POST {path} failed after {self.max_retries} attempts: {last}")

    def _get(self, s: requests.Session, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        r = s.get(f"{self.base_url}/{path}", params=params or {}, timeout=self.timeout)
        try:
            doc = r.json()
        except ValueError:
            doc = {"ok": False, "error": {"code": "NON_JSON", "message": r.text[:200]}}
        doc["_http_status"] = r.status_code
        return doc

    # -- the forbidden-field negative batch (T1) ----------------------------

    def probe_forbidden_fields(self) -> list[dict[str, Any]]:
        """Send each forbidden field and confirm ``ProfileService`` rejects it.

        Design 5.14: forbidden fields (health, fitness, mobility, medical
        device, country of birth) are "Never exported. A negative-test batch
        deliberately sends them and must be rejected by ``ProfileService``."

        Each field is sent **individually**, in an otherwise valid profile, so a
        rejection can only be attributed to that field.  Sending all five at
        once would pass even if only one were checked.
        """
        results: list[dict[str, Any]] = []
        base_profile = _minimal_valid_profile()
        for field, value in sorted(FORBIDDEN_FIELD_PROBE.items()):
            s, csrf = self._new_session()
            self._post(s, "api/consent.php", {"action": "grant", "csrf": csrf})
            body = {**base_profile, field: value, "csrf": csrf}
            doc = self._post(s, "api/profile.php", body)
            rejected = not doc.get("ok", False)
            msg = (doc.get("error") or {}).get("message", "")
            code = (doc.get("error") or {}).get("code", "")
            results.append(
                {
                    "field": field,
                    "rejected": rejected,
                    "http_status": doc.get("_http_status"),
                    "error_code": code,
                    "error_message": msg[:160],
                    "names_the_field": field in msg,
                    "expected": "rejected with the field named",
                }
            )
            # Clean up: revoke so the probe leaves no profile behind.
            self._post(s, "api/consent.php", {"action": "revoke", "csrf": csrf})
            s.close()
        return results

    # -- one participant ----------------------------------------------------

    def run_participant(
        self,
        person: PoolPerson,
        *,
        pool: str = "HRSD-pool",
        planted_position_bias: float = 0.0,
        simulated_session_date: str | None = None,
    ) -> ParticipantResult:
        t0 = time.time()
        # A panel wave carries its own simulated date and its own linked
        # person; an unlinked pool person carries neither, and is its own
        # respondent.  Read off the person rather than demanded of the caller,
        # so a batch can mix waves with different dates - which is what a wave
        # schedule across a decade is (I-075).
        if simulated_session_date is None:
            simulated_session_date = getattr(person, "simulated_session_date", None)
        res = ParticipantResult(
            pool_person_id=person.pool_person_id,
            respondent_id=str(
                getattr(person, "linked_person_id", None) or person.pool_person_id
            ),
            simulated_session_date=simulated_session_date,
            wave=getattr(person, "wave", None) or None,
            n_waves=getattr(person, "n_waves", None) or None,
        )
        traits = _traits_for_model(person)
        gen = self.tree.generator(
            Stream.MIMIC_WILLINGNESS, entity=person.pool_person_id, sim_day=0
        )
        lat_gen = self.tree.generator(
            Stream.MIMIC_LATENCY, entity=person.pool_person_id, sim_day=0
        )
        ab_gen = self.tree.generator(
            Stream.MIMIC_ABANDONMENT, entity=person.pool_person_id, sim_day=0
        )

        try:
            s, csrf = self._new_session()
        except Exception as exc:  # noqa: BLE001
            res.errors.append(f"session_init: {exc}")
            res.elapsed_s = time.time() - t0
            return res

        try:
            # ---- 1. consent -------------------------------------------------
            doc = self._post(s, "api/consent.php", {"action": "grant", "csrf": csrf})
            if not doc.get("ok"):
                res.errors.append(f"consent: {doc.get('error')}")
                return res
            res.participant_id = doc["data"]["participant_id"]
            res.consent_version = CONSENT_VERSION_TEMPLATE.format(pool=pool)

            # ---- 2. profile -------------------------------------------------
            profile = person.mimic_profile()
            doc = self._post(s, "api/profile.php", {**profile, "csrf": csrf})
            if not doc.get("ok"):
                res.errors.append(f"profile: {doc.get('error')}")
                return res
            res.mcv_position = doc["data"].get("mcv_position")

            # ---- 3. MCV, if MIMIC randomised it to 'pre' --------------------
            mcv = {
                f"mcv_{i + 1:02d}": int(v)
                for i, v in enumerate(person.traits.mcv_latent)
            }
            if res.mcv_position == "pre":
                doc = self._post(s, "api/mcv.php", {**mcv, "csrf": csrf})
                if not doc.get("ok"):
                    res.errors.append(f"mcv_pre: {doc.get('error')}")

            # ---- 4. create the session --------------------------------------
            seed = int(gen.integers(0, 2**31 - 1))
            doc = self._post(s, "api/session.php", {"action": "create", "csrf": csrf, "seed": seed})
            if not doc.get("ok"):
                res.errors.append(f"session_create: {doc.get('error')}")
                return res
            res.session_id = doc["data"].get("session_id")

            # ---- 5. answer the items ----------------------------------------
            item_index = 0
            session_length = 13
            while True:
                doc = self._get(s, "api/session.php", {"session_id": res.session_id})
                if not doc.get("ok"):
                    res.errors.append(f"session_get: {doc.get('error')}")
                    break
                data = doc["data"]
                if data.get("complete"):
                    res.completed = True
                    break
                item = data["item"]

                ckey = _context_key_of(item)
                ctx = wg.Context(
                    category=_category_of(item),
                    context_key=ckey,
                    grid_stress=0.55 if ckey == "b" else 0.10,
                    visibility=0.50 if ckey == "b" else 0.05,
                    reward=0.0,
                    comfort_cost=0.35 if _category_of(item) == "CMF" else 0.10,
                    item_index=item_index,
                    asks_seen_before=0,
                    der_owner=0.0 if person.der_ownership == ["None"] else len(person.der_ownership) / 4.0,
                    time_at_home=0.6,
                    tariff_exposure=0.3,
                )

                if wg.abandons(traits, ctx, ab_gen, session_length):
                    self._post(s, "api/session.php",
                               {"action": "abandon", "session_id": res.session_id, "csrf": csrf})
                    res.abandoned = True
                    break

                # Options as MIMIC presented them, in DISPLAY order.
                #
                # MIMIC's payload names the field ``signal`` (not
                # ``signal_code``, which is the DATABASE column name) and its
                # ``position`` is 1-BASED, because ResponseService indexes
                # ``display_order[$displayPosition - 1]``. Both were wrong on the
                # first attempt and the runner's own check caught it - "signal SO
                # not among presented options ['None']" - rather than posting a
                # position that would have recorded the wrong signal.
                options = item.get("options") or []
                display_positions = {
                    str(o.get("signal")): int(o.get("position"))
                    for o in options
                    if o.get("signal") is not None and o.get("position") is not None
                }
                if len(display_positions) != len(options):
                    res.errors.append(
                        f"item[{item_index}]: could not read signal/position from "
                        f"all {len(options)} options"
                    )
                    break
                choice = wg.choose_signal_gb(
                    traits, ctx, gen, mode="stated",
                    planted_position_bias=planted_position_bias,
                    # Positions are passed ONLY when a bias is deliberately
                    # planted (T10). Otherwise the model never sees them, which
                    # is what design 5.14 requires.
                    display_positions=(
                        {k: v - 1 for k, v in display_positions.items()}
                        if planted_position_bias else None
                    ),
                )
                chosen = choice["chosen_signal"]
                # The display position is looked up AFTER the choice, and is not
                # an input to it (design 5.14), except in T10 mode above.
                pos = display_positions.get(chosen)
                if pos is None:
                    res.errors.append(
                        f"signal {chosen} not among presented options "
                        f"{sorted(display_positions)}"
                    )
                    break

                latency = wg.response_latency_ms(
                    traits, ctx, lat_gen, deliberated=choice["deliberated"]
                )
                rdoc = self._post(
                    s, "api/response.php",
                    {
                        "session_id": res.session_id,
                        "session_item_id": item["session_item_id"],
                        "display_position": pos,
                        "latency_ms": latency,
                        "csrf": csrf,
                    },
                )
                if not rdoc.get("ok"):
                    res.errors.append(f"response[{item_index}]: {rdoc.get('error')}")
                    break
                res.n_responses += 1
                res.responses.append(
                    {
                        "participant_id": res.participant_id,
                        "session_id": res.session_id,
                        "session_item_id": item["session_item_id"],
                        "person_id": res.respondent_id,
                        "wave": res.wave,
                        "simulated_session_date": res.simulated_session_date,
                        # MIMIC's own option-order randomisation for this item,
                        # as presented: signal -> 1-based screen position.
                        "display_permutation": dict(sorted(display_positions.items())),
                        "scenario_id": item.get("scenario_id"),
                        "category_code": ctx.category,
                        "context_key": ctx.context_key,
                        "chosen_signal": chosen,
                        "display_position": pos,
                        "latency_ms": latency,
                        "is_probe": bool(item.get("is_probe")),
                        "is_probe_repeat": bool(item.get("is_probe_repeat")),
                        "is_random_item": bool(item.get("is_random_item")),
                        "probabilities": choice["probabilities"],
                        "deliberated": choice["deliberated"],
                    }
                )
                item_index += 1
                if rdoc["data"].get("complete"):
                    res.completed = True
                    break
                if item_index > 40:   # safety: MIMIC's session is 13 items
                    res.errors.append("item loop exceeded 40 items")
                    break

            # ---- 6. MCV, if randomised to 'post' ---------------------------
            if res.mcv_position == "post" and res.completed:
                doc = self._post(s, "api/mcv.php", {**mcv, "csrf": csrf})
                if not doc.get("ok"):
                    res.errors.append(f"mcv_post: {doc.get('error')}")

        except Exception as exc:  # noqa: BLE001
            res.errors.append(f"{type(exc).__name__}: {exc}")
        finally:
            s.close()
            res.elapsed_s = time.time() - t0

        # ---- D26 answer key -------------------------------------------------
        res.answer_key = {
            "participant_id": res.participant_id,
            # The RESPONDENT, which for a panel wave is the linked population
            # person and not the wave's own key.  D26's crosswalk is what makes
            # the panel a panel: group by person_id, order by
            # simulated_session_date (I-075).
            "person_id": res.respondent_id,
            "wave_person_key": person.pool_person_id,
            "wave": res.wave,
            "n_waves": res.n_waves,
            "pool": pool,
            "stratum": person.stratum,
            "true_traits": person.traits.latents(),
            "planted_segment": person.planted_segment,
            "planted_null_mode": person.planted_null_mode,
            "response_propensity": person.traits.response_propensity,
            "stated_gap": person.traits.stated_gap,
            "satisficer": bool(person.traits.satisficer),
            "planted_position_bias": planted_position_bias,
            "generator": "G-B",
            "gb_spec_hash": wg.specification_hash(),
            "simulated_session_date": simulated_session_date,
            "test_mode_settings": {
                "u19_test_mode_rate_allowance": True,
                "local_only": True,
            },
            "u18_information_lost": person.u18_information_lost,
        }
        return res

    # -- a batch ------------------------------------------------------------

    def run_batch(
        self,
        people: list[PoolPerson],
        *,
        pool: str = "HRSD-pool",
        workers: int = 12,
        planted_position_bias: float = 0.0,
        simulated_session_date: str | None = None,
        frozen_spec_path: Path | None = None,
        progress_every: int = 500,
    ) -> BatchResult:
        """Run a batch, after the safety and firewall checks.

        Participants are independent, so they parallelise cleanly.  The *content*
        of each participant's answers is addressed by their own id in the seed
        tree, so it does not depend on which worker ran them or in what order -
        only the MIMIC-side UUIDs and wall-clock timestamps vary, which U19
        accepted ("timestamps are run-time", with the simulated date carried in
        D26).
        """
        if self.sandbox is not None:
            assert_local_only(self.sandbox, self.base_url)
        if frozen_spec_path is not None:
            wg.assert_frozen(frozen_spec_path)

        t0 = time.time()
        results: list[ParticipantResult] = []
        errors: list[str] = []
        done = 0

        def one(person: PoolPerson) -> ParticipantResult:
            return self.run_participant(
                person, pool=pool,
                planted_position_bias=planted_position_bias,
                simulated_session_date=simulated_session_date,
            )

        with cf.ThreadPoolExecutor(max_workers=workers) as pool_ex:
            futures = {pool_ex.submit(one, p): p for p in people}
            for fut in cf.as_completed(futures):
                try:
                    results.append(fut.result())
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{futures[fut].pool_person_id}: {exc}")
                done += 1
                if progress_every and done % progress_every == 0:
                    rate = done / max(time.time() - t0, 1e-9)
                    print(
                        f"  {done}/{len(people)} participants "
                        f"({rate:.1f}/s, {len(errors)} hard errors)",
                        flush=True,
                    )

        # Sorted so the recorded order is a function of the input, not of
        # thread completion order.
        results.sort(key=lambda r: r.pool_person_id)

        # The five 5.14 counters count RESPONDENTS, not sessions and not MIMIC
        # participant rows.  The E1 report states the rule - "repeated sessions
        # never count as unique participants" - and with I-075's wave schedule
        # it finally bites: one linked person holds 8 to 15 MIMIC participant
        # records, because MIMIC's public API allows one session each (I-087).
        # Counting participant rows here would have inflated
        # `unique_synthetic_participants` from 11,664 to about 22,000 and turned
        # the E1 target into an artefact of repeat interviewing.
        unique = len({r.respondent_id for r in results if r.participant_id})
        n_participant_rows = len({r.participant_id for r in results if r.participant_id})
        _dates = [r.simulated_session_date for r in results
                  if r.simulated_session_date]
        counters = MimicCounters(
            unique_participants=unique,
            completed_sessions=sum(1 for r in results if r.completed),
            completed_responses=sum(r.n_responses for r in results),
            linked_panel_participants=unique if pool == "BN-panel" else 0,
            unlinked_pool_participants=unique if pool == "HRSD-pool" else 0,
            abandoned_sessions=sum(1 for r in results if r.abandoned),
        )
        return BatchResult(
            counters=counters, participants=results, errors=errors,
            elapsed_s=time.time() - t0,
            config={
                "pool": pool, "workers": workers,
                "planted_position_bias": planted_position_bias,
                "base_url": self.base_url,
                "gb_spec_hash": wg.specification_hash(),
                "n_requested": len(people),
                "n_mimic_participant_rows": n_participant_rows,
                "n_dated_sessions": len(_dates),
                "n_distinct_simulated_session_dates": len(set(_dates)),
                "simulated_session_date_span": (
                    [min(_dates), max(_dates)] if _dates else []
                ),
            },
        )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _category_of(item: dict[str, Any]) -> str:
    cat = item.get("category_code")
    if cat:
        return str(cat)
    sid = str(item.get("scenario_id", ""))
    return sid.split("-", 1)[0] if "-" in sid else "ERF"


def _context_key_of(item: dict[str, Any]) -> str:
    """The factorial context key ('a' normal, 'b' higher pressure / observability).

    MIMIC's ``api/session.php`` does **not** return ``context_key``, even though
    ADR-006 added it as a column on ``session_items`` and persists it there. The
    payload carries only the human-readable ``context_label``. So an API-only
    consumer has to recover it from the scenario id, whose last segment is the
    context key by construction (``DAP-04-b`` is DAP scenario 04 in context b).

    This matters beyond tidiness: test T7 estimates a context effect (AMCE), and
    getting the context wrong would attribute the effect to the wrong arm. The
    first version defaulted every item to 'a', which would have made the planted
    context effect unrecoverable. Recorded as I-024.
    """
    key = item.get("context_key")
    if key in ("a", "b"):
        return str(key)
    sid = str(item.get("scenario_id", ""))
    tail = sid.rsplit("-", 1)[-1].strip().lower() if "-" in sid else ""
    return tail if tail in ("a", "b") else "a"


def _traits_for_model(person: PoolPerson) -> dict[str, Any]:
    tv = person.traits
    out = dict(tv.latents())
    out.update(
        {
            "stated_gap": tv.stated_gap,
            "attention": tv.attention,
            "age": float(person.age),
            "education_z": {
                "ISCED 0": -2.0, "ISCED 1": -1.4, "ISCED 2": -0.8, "ISCED 3": -0.2,
                "ISCED 4": 0.2, "ISCED 5": 0.6, "ISCED 6": 1.0, "ISCED 7": 1.5,
                "ISCED 8": 2.0,
            }.get(person.education_level, 0.0),
            "digital_z": {"High": 1.0, "Medium": 0.0, "Low": -1.0}.get(
                person.digital_access, 0.0
            ),
        }
    )
    return out


def _minimal_valid_profile() -> dict[str, Any]:
    """A profile that MIMIC accepts, used as the base for the forbidden probe."""
    return {
        "age_band": "35–44",
        "sex": "Female",
        "household_size": "2",
        "children_present": "No",
        "employment_status": "Full-time",
        "work_pattern": "Office",
        "dwelling_type": "Semi-Detached",
        "ownership_status": "Owner",
        "region_country": "IE",
        "region_nuts3": "IE053",
        "urban_rural_island": "Urban",
        "income_band": "3",
        "der_ownership": ["None"],
        "environmental_concern": 3,
        "trust_in_automation": 3,
        "comfort_sensitivity": 3,
    }
