"""The dataset catalogue, generated from the files on disk.

``DATASETS.md`` at the repository root is written by this module and by nothing
else. It exists because the question "what is actually in v1, and how much of
it" had no answer that could be read in one place: the schema says what a
dataset *should* contain, the design says what it is *for*, and only the files
say what is *there*. Those three disagree, and the disagreement is the most
useful thing in the document — Appendix D lists it.

**Every figure comes from the files.** Row counts come from each Parquet
footer, byte counts from ``stat()``, column lists from the file schema, and
ranges from Parquet column statistics, which carry an exact min, max and null
count per row group and so give a true extreme without reading 578 MB. Time
spans come from the statistics of the timestamp columns. The only numbers not
taken from a file are the ones in this docstring.

**Prose is prose.** The per-dataset description and key points are written
here, drawn from design revision 4's dataset table (§6.1) and its access-class
rules, and they deliberately contain **no numbers**: a sentence with a figure
in it would be a figure not traceable to a file, and the rule for this document
is that where there is no artefact there is no number.

Regenerate with::

    ./.venv/bin/python -m baile_nua.report.datasets_md

It is read-only on ``v1/``.
"""

from __future__ import annotations

import dataclasses
import datetime
import json
import re
import subprocess
from pathlib import Path
from typing import Any

__all__ = ["build_catalogue", "render", "write_markdown", "main"]

PAGE_BREAK = '<div style="page-break-after: always;"></div>'

#: Columns whose VALUES are withheld from the sample tables. The brief's rule
#: is identifiers only, no derived identities, and it is implemented as a
#: pattern list rather than a column list so a dataset that lands later is
#: covered without anyone remembering to extend this. None of the five
#: datasets currently on disk carries any of them; that is the point of
#: writing it before they do.
IDENTITY_PATTERNS: tuple[str, ...] = (
    "name", "dob", "date_of_birth", "birth_date", "address", "eircode",
    "postcode", "phone", "email", "narrative", "biography", "text",
)

#: Where a dataset's rows live when they are not a released Parquet part.
#: Discovered rather than declared: every artefact under v1/evidence is
#: scanned for a top-level list keyed ``dNN_*``, which is the convention the
#: ten-year aggregate already uses, so a new artefact carrying rows is picked
#: up without a change here.
EVIDENCE_ROW_KEY = re.compile(r"^d(\d{2})_")

#: Datasets whose absence from v1/ has a reason recorded ON DISK, in
#: v1/evidence/delivery_packages.json. Read from that file; this maps its keys
#: onto dataset ids, which is the one piece the file leaves implicit.
NOT_SHIPPED_KEYS: dict[str, tuple[str, ...]] = {
    "D27": ("D27",),
    "D28": ("D28_to_D31",),
    "D29": ("D28_to_D31",),
    "D30": ("D28_to_D31",),
    "D31": ("D28_to_D31",),
}

# --------------------------------------------------------------------------- #
# prose
# --------------------------------------------------------------------------- #

#: description + key points per dataset. Numbers are forbidden here.
PROSE: dict[str, dict[str, Any]] = {
    "D01": {
        "description": (
            "The town's geography: parcels, streets, venues and the topology "
            "of the low-voltage network. It is the substrate every other "
            "dataset refers to when it says where something is, and it does "
            "not change during a run."
        ),
        "points": [
            "One row is one geographic feature — a parcel, a street segment, "
            "a venue or a network element.",
            "Built once at t0 from the small-area boundaries and the venue "
            "stock, then held fixed.",
            "Carries the feature geometry, so it is the only dataset whose "
            "declared storage is GeoParquet rather than Parquet.",
            "Ground truth: the network topology tells a model where the "
            "constraints are, which is part of what a network model is "
            "supposed to infer.",
        ],
    },
    "D02": {
        "description": (
            "Every dwelling's fabric, archetype, BER, heating system and the "
            "physics parameters derived from them. This is the input the "
            "thermal model solves and the truth that a building-stock "
            "estimator is trying to recover."
        ),
        "points": [
            "One row is one building at one version; a passport event in D03 "
            "closes a version and opens the next.",
            "The element U-values are derived from the assessed-fabric "
            "source, which is why that source can calibrate the model and "
            "cannot validate it.",
            "Holds both the as-built and the current state, so a retrofit's "
            "before and after are both recoverable.",
            "Ground truth. The observable counterparts are the recorded "
            "metadata in D30, which is stale and wrong at realistic rates.",
            "Must not be joined to an observable dataset to score a model "
            "that was given D30: that compares a model against its own input.",
        ],
    },
    "D03": {
        "description": (
            "The building passport: dated events that change a dwelling — an "
            "extension, a fabric retrofit, an asset added or removed. Each "
            "event changes the physics from its own date onward rather than "
            "from the start of the year it falls in."
        ),
        "points": [
            "One row is one dated change to one building.",
            "Drives the dwelling's version history in D02 and the asset "
            "lifetimes in D04.",
            "Has a redacted observable view: that an event occurred and when, "
            "without the parameters that say what it did.",
            "The un-redacted form is ground truth — it is the answer to the "
            "change-detection task that D20 scores.",
        ],
    },
    "D04": {
        "description": (
            "Appliances, heating plant, PV, batteries, chargers and vehicles, "
            "each with an owner and a lifetime. It is where a device comes "
            "from and when it stops existing."
        ),
        "points": [
            "One row is one asset at one version, owned by a household or a "
            "building.",
            "Lifetimes are dated, so an asset installed mid-run is absent "
            "before its date and present after it.",
            "The appliance rows are what the cycle generator draws from, and "
            "they key into the signature library in D22.",
            "Ground truth. Observable traces of these assets appear in D18, "
            "D19 and the recorded metadata in D30.",
        ],
    },
    "D05": {
        "description": (
            "The persons dataset, HRSD_Occupants proper: each resident's "
            "persistent characteristics and trait vector. It is the "
            "population the whole simulation is about."
        ),
        "points": [
            "One row is one person, with the attributes that do not change "
            "and the latent traits that drive behaviour.",
            "Synthesised to match the published small-area marginals for "
            "Cobh, with the age by economic-status joint conditioned on a "
            "county-level source.",
            "Traits are latent by construction: no observable dataset carries "
            "them, and the MIMIC answer key in D26 is the only place they are "
            "crosswalked.",
            "Ground truth, and the most sensitive in the release: a model "
            "given D05 has been given the answer to every inference task in "
            "the privacy threat model.",
            "Must never reach a model under test, and must not be joined to "
            "D25 outside the scoring service.",
        ],
    },
    "D06": {
        "description": (
            "Household membership over time: who lives where, from when to "
            "when. Every household-level quantity in the release is only "
            "well defined against this dataset."
        ),
        "points": [
            "One row is one person's residence in one household over one "
            "interval.",
            "Opened and closed by the move, birth, death and separation "
            "events in D09.",
            "An interval-valued dataset, so a household's size on a given "
            "day is a query rather than a column.",
            "Ground truth: occupancy is the quantity the privacy threat "
            "model treats as the thing an attacker wants.",
        ],
    },
    "D07": {
        "description": (
            "The relationship graph: kin, partner, carer, friend and "
            "co-worker edges between people, valid over intervals. It is what "
            "makes a household a household rather than a set of people in a "
            "building."
        ),
        "points": [
            "One row is one directed or undirected edge over one interval.",
            "Partnering and separation events in D09 create and end the "
            "partner edges; caring load follows the carer edges.",
            "Edges are what joint activity planning reads when it decides "
            "that two people do something together.",
            "Ground truth, and re-identifying in combination: a graph of this "
            "kind is distinctive even without attributes.",
        ],
    },
    "D08": {
        "description": (
            "Person states that evolve slowly — employment, health, caring "
            "load, work pattern — recorded as slowly changing dimensions so "
            "that every state has a from and a to."
        ),
        "points": [
            "One row is one person's state over one interval, closed when the "
            "state changes.",
            "Transitions are driven by the dated hazards in the life-course "
            "module and appear as events in D09.",
            "Distinguishes the persistent layer in D05 from the evolving "
            "layer here, which is what lets a biography be reconstructed.",
            "Ground truth: health state in particular is a special category "
            "of personal data in the real world and is treated as the most "
            "sensitive field in the synthetic one.",
        ],
    },
    "D09": {
        "description": (
            "Life events: births, deaths, moves, job changes, health-state "
            "onsets and household decisions, each with its date and the "
            "people it involves. It is the spine of the life-course model and "
            "the reason the town changes over a decade."
        ),
        "points": [
            "One row is one event, dated, typed, and tied to the person or "
            "household it happened to.",
            "Every event type is driven by a hazard that is either taken from "
            "an Irish published rate or flagged as an assumption with a "
            "search record.",
            "Events are what open and close the intervals in D06 and D08, so "
            "this dataset and those two must reconcile exactly.",
            "Ground truth. The observable consequence of an event is a change "
            "in the load, which is what a detector is asked to find.",
            "Must not be used as a feature by a model whose task is to detect "
            "the events it records.",
        ],
    },
    "D10": {
        "description": (
            "Activity intervals: what each person is doing, where, and with "
            "whom. Appliance use, presence and the heating demand all follow "
            "from it, so it is the layer where behaviour becomes energy."
        ),
        "points": [
            "One row is one person doing one thing over one interval.",
            "Timings are driven by time-use participation curves and are not "
            "adjusted to match any load profile.",
            "Carries co-participants, so a joint activity is recoverable "
            "rather than inferred from coincidence.",
            "Partitioned by year and month in its declared storage, because a "
            "town-decade of activity intervals is too large for one file.",
            "Ground truth: an activity label is the thing a non-intrusive "
            "load-monitoring model is trying to produce.",
        ],
    },
    "D11": {
        "description": (
            "Presence: where each person is over each interval, at home or "
            "away and at which venue. It is the source the no-double-occupancy "
            "invariant is checked against."
        ),
        "points": [
            "One row is one person in one place over one interval.",
            "Derived from the activity intervals, with outdoor-but-at-home "
            "activities recorded at the person's own building rather than at "
            "a venue.",
            "Collected for the opening days of a run rather than the whole "
            "year: a year of minute-resolution presence for the estate is "
            "tens of millions of rows and no check reads them.",
            "Ground truth, and the direct target of the occupancy-inference "
            "attack measured in the privacy artefact.",
            "Must not appear, in any aggregated form, in a dataset sent to a "
            "device or an evaluator.",
        ],
    },
    "D12": {
        "description": (
            "Trips: origin, destination, mode, vehicle and distance. It "
            "connects the activity layer to the vehicle layer, and it is what "
            "makes an electric vehicle's state of charge a consequence of "
            "someone's day rather than a schedule."
        ),
        "points": [
            "One row is one trip by one person.",
            "Generated from the activity sequence, so a trip exists only "
            "where an activity requires someone to be somewhere else.",
            "Drives vehicle energy use, including the cold-weather "
            "consumption penalty.",
            "Ground truth: trip patterns are among the most re-identifying "
            "data about a person that exists.",
        ],
    },
    "D13": {
        "description": (
            "Appliance cycles: when each appliance ran, on which programme, "
            "with which signature and how much energy it used. It is the "
            "answer key for load disaggregation."
        ),
        "points": [
            "One row is one cycle of one appliance.",
            "Cycles are placed by the activity that calls for them, not by a "
            "diary, so a wash follows someone deciding to do laundry.",
            "Carries the signature identifier, which keys into the signature "
            "library in D22 and makes the waveform reproducible.",
            "Ground truth. The observable counterpart is the aggregate in "
            "D18 and D19, which is what a disaggregation model is given.",
            "Must not be joined to D18 by a model under test: that is the "
            "label it is being asked to predict.",
        ],
    },
    "D14": {
        "description": (
            "Calendar events: holidays, school terms, storms, outages and the "
            "rest, each with its phases, footprint and attendance. It is the "
            "shared context that makes many households change behaviour on "
            "the same day."
        ),
        "points": [
            "One row is one instance of one event kind, with its phase and "
            "spatial footprint.",
            "Every declared kind must occur in a full year, and each one has "
            "a source or a registered assumption; the event coverage audit "
            "checks both.",
            "Footprint matters: a storm is town-wide, a school term applies "
            "to households with children, an outage is a feeder.",
            "Ground truth as the event list, though the fact of a storm or a "
            "bank holiday is also in the external series in D31.",
        ],
    },
    "D15": {
        "description": (
            "The true site weather and solar geometry that drives the "
            "physics: temperature, irradiance, wind, humidity and rain at "
            "minute resolution. It is what the building actually experienced."
        ),
        "points": [
            "One row is one minute of site weather.",
            "Downscaled from the published station records for the two "
            "stations nearest the town.",
            "Ground truth, and distinct from D31: the observable station "
            "weather has outages, gap-fills and the station's own location.",
            "A model given D15 has been given a weather input no real "
            "operator has, which is why the observable series is a separate "
            "dataset rather than a flag on this one.",
        ],
    },
    "D16": {
        "description": (
            "Building state at minute resolution: zone temperatures, relative "
            "humidity, CO₂, the hot water cylinder and the heat delivered. It "
            "is the physics model's own output and the state that carries "
            "across the day boundary."
        ),
        "points": [
            "One row is one building at one minute.",
            "Checkpointed daily, so any single day can be restored and "
            "re-simulated; the replay test compares exactly this dataset "
            "against a restored re-run.",
            "Holds the cylinder temperature as well as the fabric "
            "temperatures, because both carry overnight and a restore that "
            "forgot either would diverge by morning.",
            "Ground truth: indoor temperature is what a thermal-model "
            "estimator is trying to infer from the load.",
            "Comfort claims must not be read from it as though it were "
            "measured — it is the model's own state, not an observation.",
        ],
    },
    "D17": {
        "description": (
            "Network state: feeder and transformer loading, voltages and "
            "outages at minute resolution, from the quasi-static power flow. "
            "It is the electrical consequence of everything the households do."
        ),
        "points": [
            "One row is one network element at one minute.",
            "Produced by solving the network at the coupling epoch, so it "
            "exists only for runs in the coupled mode.",
            "Has an aggregate observable view — feeder and transformer totals "
            "rather than per element — because per-element state would hand a "
            "model the answer to the state-estimation task.",
            "The voltages are not a validated claim: the topology is an "
            "assumption, and the module refuses to let them be quoted as one.",
            "Ground truth per element; the aggregate view is the released "
            "form.",
        ],
    },
    "D17_aggregate": {
        "description": (
            "D17's observable view: what a distribution operator would "
            "actually hold about its low-voltage network. The connection "
            "register — which MPRN sits on which feeder and which "
            "substation — the asset register's transformer and feeder "
            "ratings, and the feeder-head and substation power measurements."
        ),
        "points": [
            "Three kinds of row in one table, told apart by `record_kind`: a "
            "connection-register entry, a feeder-head measurement, or a "
            "substation measurement. The register is written once per run, "
            "because the topology is built once and does not change within "
            "it.",
            "Both ratings are catalogue values of the pandapower standard "
            "types the network is built from, so neither is a number written "
            "in this build.",
            "No voltage, anywhere. The topology is a declared assumption and "
            "voltage drop is a line integral along exactly the declared "
            "feeder span, so publishing a per-unit voltage to a model "
            "developer would present an assumption as a measurement.",
            "No per-element loading: that ratio is ground truth. The ratings "
            "and the measurements are both here because the change request "
            "names them; their ratio is not published.",
            "No per-connection power. A register row names a premises and "
            "carries no measurement; a measurement row names an element and "
            "never a premises.",
            "Every measured power equals the ground-truth row for the same "
            "element and epoch exactly: the view is a projection of the "
            "truth, not a second computation of it. Observable, so this is "
            "what a model developer is given.",
        ],
    },
    "D18": {
        "description": (
            "Observations: the rendered device readings, with the noise, "
            "quantisation, clock error and gaps that real meters and sensors "
            "produce. This is what a sensor would have seen, and it is the "
            "principal observable dataset."
        ),
        "points": [
            "One row is one reading from one channel at one device-native "
            "timestamp.",
            "Rendered from the ground-truth series through a declared error "
            "model per channel, with a provenance code and a quality flag on "
            "every value.",
            "Carries a sensor tier per premises, so a home with a cheap meter "
            "and a home with a research-grade one are different in the data "
            "rather than in a footnote.",
            "Observable: this is the dataset a model under test is given.",
            "It is the largest dataset in the release by a wide margin, which "
            "is why the ten-year slice omits it.",
        ],
    },
    "D19": {
        "description": (
            "Edge exports: what actually leaves each home across the meter "
            "boundary, at the settlement interval, under each of the declared "
            "export configurations. It is the network-side observable, and "
            "the one the privacy work is about."
        ),
        "points": [
            "One row is one premises over one settlement interval under one "
            "export configuration.",
            "The configurations differ in what they reveal, and a "
            "configuration that claims to reveal less must contain less — "
            "which is tested against the others rather than against the "
            "schema.",
            "The compliance-only configuration deliberately carries no "
            "interval energy at all, so its energy columns are null by "
            "design and the requirement on them is conditional.",
            "Observable, and the input to the occupancy-inference attack: the "
            "finer the interval, the more an attacker recovers.",
            "The export configuration column must be filtered before any "
            "aggregate is computed, or the same home is counted several times.",
        ],
    },
    "D20": {
        "description": (
            "Change labels: the ground-truth onset, type and persistence of "
            "every change a detector could be asked to find. It is the "
            "scoring key for the change-detection task."
        ),
        "points": [
            "One row is one labelled change, with its onset date, class and "
            "whether it persists.",
            "Labels are tiered by how observable the change is, so a scoring "
            "service can report performance separately for the easy and the "
            "hard ones.",
            "Derived from the life events in D09 and the passport events in "
            "D03, and must reconcile with both.",
            "Scoring API only, never released: its own schema says so, and a "
            "model that has seen it has seen the answers.",
        ],
    },
    "D21": {
        "description": (
            "Biographies: human-readable narratives of each person's life, "
            "generated from the persistent, evolving and event datasets. They "
            "exist so a reader can sanity-check a synthetic life that no "
            "aggregate check would catch as implausible."
        ),
        "points": [
            "One row is one person at one date, as text.",
            "Generated from the other datasets rather than authored, so a "
            "biography that reads strangely is evidence about the model.",
            "Declared as JSON or Markdown rather than Parquet, because the "
            "payload is prose.",
            "Ground truth, and free text: it contains, in readable form, "
            "everything the structured ground truth contains.",
        ],
    },
    "D22": {
        "description": (
            "The signature library: appliance waveform templates and the "
            "parameters that vary them. It is metadata rather than data about "
            "the town — the same library would serve another town."
        ),
        "points": [
            "One row is one appliance signature template.",
            "Keyed by the signature identifier that appears on every cycle in "
            "D13, which is what makes a cycle's waveform reproducible.",
            "Declared as Parquet alongside compressed arrays, because a "
            "waveform is a vector rather than a scalar.",
            "Metadata: it ships in the evidence package, not with the data.",
        ],
    },
    "D23": {
        "description": (
            "Run manifests: the code and data versions, parameters, seeds and "
            "checksums for every run. It is what makes a figure in a report "
            "traceable to the run that produced it."
        ),
        "points": [
            "One row is one run.",
            "Records the master seed and the library versions, because a run "
            "whose dependency versions are unknown cannot be reproduced.",
            "Held as JSON in the repository as well as in the object store, "
            "so the provenance survives the data being moved.",
            "Metadata, and the first thing to read when two runs disagree.",
        ],
    },
    "D24": {
        "description": (
            "Calibration targets: every empirical quantity the model is "
            "calibrated or compared against, with its source, version, "
            "tolerance and exposure class. It is the register that decides "
            "which checks count as independent."
        ),
        "points": [
            "One row is one target statistic from one source.",
            "Carries the exposure class, which is what separates a check that "
            "validates the model from one that reports the model agreeing "
            "with its own input.",
            "Every target names a file in the sources tree, so no calibration "
            "number in the project is unsourced.",
            "Metadata: it ships in the evidence package with the sources "
            "themselves.",
        ],
    },
    "D25": {
        "description": (
            "The MIMIC export: HRSD participants, profiles, moral-choice "
            "vectors, sessions and responses, delivered through the MIMIC API "
            "in its own schema. It is the stated-preference half of the "
            "project, beside the measured half."
        ),
        "points": [
            "One row is a participant, a session or a response, depending on "
            "the table.",
            "Delivered through the MIMIC API against a local instance, never "
            "a remote or production one.",
            "A subset of participants is linked to the synthetic population; "
            "the rest are an unlinked pool, so a linkage attack cannot assume "
            "every participant is a resident.",
            "Observable on the MIMIC side: this is what a researcher "
            "analysing the panel would hold.",
            "The crosswalk back to a person is in D26 and is not part of this "
            "dataset.",
        ],
    },
    "D26": {
        "description": (
            "The MIMIC answer key: the crosswalk from participant to person, "
            "the true traits, the planted segments, response propensity and "
            "stated-preference gap. It is how a panel analysis is scored."
        ),
        "points": [
            "One row is one participant.",
            "Holds the planted structure — the segments and effects a correct "
            "analysis should recover — which is what makes the panel a test "
            "rather than a dataset.",
            "Carries the stated-against-revealed gap per participant, so a "
            "model that assumes stated preference predicts behaviour can be "
            "shown to be wrong by construction.",
            "Scoring only. Releasing it would make every MIMIC test "
            "unfalsifiable.",
        ],
    },
    "D27": {
        "description": (
            "Tariffs and contracts: each home's supplier tariff, "
            "time-of-use and export rates, switch dates, flexibility and "
            "peer-to-peer contract terms, and its connection limits. It is "
            "the commercial context a flexibility model needs."
        ),
        "points": [
            "One row is one home over one interval of one contract.",
            "Includes the import and export capacity limits, so a dispatch "
            "that would breach the connection is representable as a breach.",
            "Switch dates matter: a home that changed supplier mid-run has "
            "two tariffs, and a model that assumes one will misprice it.",
            "Observable — it is what a utility or an aggregator would hold — "
            "while the market rules themselves are metadata.",
        ],
    },
    "D28": {
        "description": (
            "The study protocol: recruitment, response rates, consent to "
            "sensors, dropouts, trial arms and periods. It is the "
            "administrative record of how the data came to exist, and the "
            "mechanism by which it is incomplete."
        ),
        "points": [
            "One row is one premises and one protocol event — recruited, "
            "consented, installed, dropped out.",
            "The selection mechanism is ground truth: who joins the study is "
            "not random, and a model that ignores that will generalise badly "
            "from the sample.",
            "Carries incomplete consent records, installer delays and "
            "arm-assignment deviations, because real protocols have all three.",
            "Observable as the record; the reason behind each gap is not "
            "observable.",
        ],
    },
    "D29": {
        "description": (
            "The household survey: questionnaire answers with calibrated "
            "reporting error and non-response. It is what people say, as "
            "distinct from what the sensors recorded."
        ),
        "points": [
            "One row is one premises in one survey wave.",
            "Error is modelled rather than added: unit and item non-response "
            "that depends on circumstances, social-desirability bias, recall "
            "error, satisficing and answers going stale between waves.",
            "The true values are in the ground-truth datasets, which is what "
            "makes the reporting error measurable rather than assumed.",
            "Observable. The gap between a survey answer and the truth is one "
            "of the things the release exists to let people study.",
        ],
    },
    "D30": {
        "description": (
            "Recorded metadata: the BER, floor area, PV capacity, dates, "
            "orientation and shading as some administrative record holds "
            "them — stale or wrong at realistic rates. It is the building "
            "data a real analyst actually gets."
        ),
        "points": [
            "One row is one premises at one version of the record.",
            "Wrong in the ways records are wrong: missing fields, values that "
            "predate a retrofit, unit and transcription errors, conflicts "
            "between assessor and installer, and records for assets since "
            "removed.",
            "The true values are in D02 and D04, so the error can be "
            "quantified instead of asserted.",
            "Observable, and the right input for any model whose real-world "
            "counterpart would be given a BER certificate rather than a "
            "fabric model.",
        ],
    },
    "D31": {
        "description": (
            "External series: station weather, wholesale prices, carbon "
            "intensity, system demand and flexibility-service events. It is "
            "the published context anyone could download, with the defects "
            "published data has."
        ),
        "points": [
            "One row is one observation of one series at its own native "
            "resolution.",
            "Distinct from D15: this is the station's reading, with outages "
            "and gap-filled values, not the weather at the dwelling.",
            "Includes revised and later-corrected values, so a model trained "
            "on the first publication of a price series can be shown to have "
            "used data that no longer exists.",
            "Observable, and the only observable dataset whose contents are, "
            "in the real world, public.",
        ],
    },
}


# --------------------------------------------------------------------------- #
# disk facts
# --------------------------------------------------------------------------- #

@dataclasses.dataclass
class ColumnFacts:
    name: str
    physical_type: str
    logical_type: str
    nulls: int
    rows: int
    minimum: Any = None
    maximum: Any = None

    @property
    def nullable_in_practice(self) -> str:
        if self.rows == 0:
            return "—"
        if self.nulls == 0:
            return "no nulls"
        return f"{self.nulls:,} null ({self.nulls / self.rows:.1%})"


@dataclasses.dataclass
class DiskFacts:
    dataset_id: str
    parts: list[Path] = dataclasses.field(default_factory=list)
    manifests: list[Path] = dataclasses.field(default_factory=list)
    rows: int = 0
    n_bytes: int = 0
    columns: list[ColumnFacts] = dataclasses.field(default_factory=list)
    package_dir: str = ""
    manifest: dict[str, Any] = dataclasses.field(default_factory=dict)
    elsewhere: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    resolution: str = "not derived"
    time_span: str = "—"
    sample: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    sample_populated: list[dict[str, Any]] = dataclasses.field(
        default_factory=list)
    sample_populated_column: str = ""
    #: ``{run: {parts, rows, bytes}}`` for runs other than the estate-year.
    #: A dataset present only for another run is PRESENT - the rows exist as
    #: Parquet - and the page says which run. Before this, moving D03, D09 and
    #: D20 into the run they describe (I-091) made them read "partial", which
    #: described the scan rather than the release.
    other_runs: dict[str, Any] = dataclasses.field(default_factory=dict)

    @property
    def status(self) -> str:
        if self.parts or self.other_runs:
            return "present"
        if self.elsewhere:
            return "partial"
        return "missing"


def _arrow_leaves(schema: Any) -> dict[str, tuple[str, bool]]:
    """Leaf path -> (readable Arrow type, nullable), struct columns flattened.

    The Parquet footer flattens a struct into its leaves, so the footer's
    column list and the file's logical column list are different things.
    D19 is the case that matters: ``building_energy_profile`` is a struct of
    three fields, so the footer reports fourteen columns where the dataset has
    twelve. Reading the footer alone made the generator report the struct as
    declared-but-absent and its three leaves as undeclared extras, which was
    wrong in both directions. The leaf PATH is used throughout, because that
    is the name statistics are keyed by and it shows the real shape.
    """
    import pyarrow as pa

    out: dict[str, tuple[str, bool]] = {}

    def walk(field: Any, prefix: str = "") -> None:
        name = f"{prefix}{field.name}"
        if pa.types.is_struct(field.type):
            for child in field.type:
                walk(child, f"{name}.")
            return
        out[name] = (str(field.type), bool(field.nullable))

    for f in schema:
        walk(f)
    return out


#: Unit by column-name suffix, resolved against the schema's own units block.
#: The schema declares units per QUANTITY and only some fields repeat them per
#: field, so a unit shown here is either declared or derived from the name,
#: and the table says which.
UNIT_SUFFIXES: tuple[tuple[str, str], ...] = (
    ("_wh", "energy"), ("_kwh", "energy"), ("_w", "power"), ("_kw", "power"),
    ("_c", "temperature"), ("_pct", "relative_humidity"), ("_ppm", "co2"),
    ("_km", "distance"),
)


def _derived_unit(column: str, units: dict[str, str]) -> str | None:
    name = column.rsplit(".", 1)[-1].lower()
    for suffix, quantity in UNIT_SUFFIXES:
        if name.endswith(suffix):
            value = units.get(quantity)
            if suffix == "_kwh" and value == "Wh":
                return "kWh"
            if suffix == "_kw" and value == "W":
                return "kW"
            if suffix == "_pct":
                return "percent"
            return value
    return None


def _scan_dataset(parts: list[Path]) -> tuple[int, int, list[ColumnFacts]]:
    """Rows, bytes and per-column facts, from the Parquet footers only.

    Column statistics carry an exact minimum, maximum and null count for every
    row group, so the extremes reported here are the true extremes of the file
    and no data pages are read. On the largest dataset in the release that is
    the difference between a second and several minutes.
    """
    import pyarrow.parquet as pq

    rows = 0
    n_bytes = 0
    acc: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for path in parts:
        n_bytes += path.stat().st_size
        pf = pq.ParquetFile(path)
        md = pf.metadata
        rows += md.num_rows
        leaves = _arrow_leaves(pf.schema_arrow)
        for i in range(md.num_columns):
            name = md.schema.column(i).path
            if name not in acc:
                order.append(name)
                arrow_type, nullable = leaves.get(
                    name, (str(md.schema.column(i).physical_type), True))
                acc[name] = {
                    "physical_type": str(md.schema.column(i).physical_type),
                    "logical_type": arrow_type, "declared_nullable": nullable,
                    "nulls": 0, "min": None, "max": None, "has_stats": False,
                }
            entry = acc[name]
            for g in range(md.num_row_groups):
                col = md.row_group(g).column(i)
                st = col.statistics
                if st is None:
                    continue
                entry["has_stats"] = True
                entry["nulls"] += int(st.null_count or 0)
                if st.has_min_max:
                    lo, hi = st.min, st.max
                    entry["min"] = lo if entry["min"] is None else min(entry["min"], lo)
                    entry["max"] = hi if entry["max"] is None else max(entry["max"], hi)
    cols = [
        ColumnFacts(
            name=n, physical_type=acc[n]["physical_type"],
            logical_type=acc[n]["logical_type"], nulls=acc[n]["nulls"],
            rows=rows,
            minimum=acc[n]["min"] if acc[n]["has_stats"] else None,
            maximum=acc[n]["max"] if acc[n]["has_stats"] else None,
        )
        for n in order
    ]
    return rows, n_bytes, cols


#: Timestamp-ish column names, in the order they are preferred for a span.
TIME_COLUMNS = (
    "interval_start", "ts", "timestamp", "start_ts", "event_date", "date",
    "onset_date", "start_min",
)


def _span_and_resolution(parts: list[Path], cols: list[ColumnFacts]
                         ) -> tuple[str, str]:
    """The time span from column statistics; the spacing from a small read.

    The span is exact, because it comes from the footers. The spacing is
    labelled as derived from a sample, because establishing a modal interval
    needs values rather than extremes and reading the whole dataset to confirm
    what a thousand rows already say is not a good use of the disk.
    """
    import pyarrow.parquet as pq

    by_name = {c.name: c for c in cols}
    tcol = next((n for n in TIME_COLUMNS if n in by_name), None)
    if tcol is None:
        return "—", "not a time series"
    c = by_name[tcol]
    if c.minimum is None:
        return "—", "not derived"
    span = f"`{tcol}` {c.minimum} → {c.maximum}"

    # Spacing. For an interval dataset the duration is a column difference and
    # needs no grouping; otherwise take one entity's successive timestamps.
    try:
        pf = pq.ParquetFile(parts[0])
        want = [tcol]
        names = {cc.name for cc in cols}
        if "interval_end" in names:
            want.append("interval_end")
        key = next((k for k in ("premises_id", "building_id", "person_id",
                                "household_id") if k in names), None)
        if key:
            want.append(key)
        batch = next(pf.iter_batches(batch_size=20_000, columns=want))
        tab = batch.to_pydict()
        if "interval_end" in want:
            durs = {
                (b - a).total_seconds() / 60.0
                for a, b in zip(tab[tcol], tab["interval_end"])
                if a is not None and b is not None
            }
            if durs:
                shown = ", ".join(f"{d:g}" for d in sorted(durs)[:4])
                return span, (
                    f"{shown} min interval"
                    + ("s (mixed; filter the view column)" if len(durs) > 1
                       else "")
                )
        if key:
            first = tab[key][0]
            seq = [t for t, k in zip(tab[tcol], tab[key]) if k == first]
            deltas = sorted({
                (b - a).total_seconds() / 60.0
                for a, b in zip(seq, seq[1:]) if a is not None and b is not None
            })
            pos = [d for d in deltas if d > 0]
            if pos:
                return span, (
                    f"{pos[0]:g} min between rows for one "
                    f"{key.replace('_id', '')} (derived from a sample)"
                )
    except Exception as exc:                                  # pragma: no cover
        return span, f"not derived ({type(exc).__name__})"
    return span, "not derived"


def _sample(parts: list[Path], cols: list[ColumnFacts], n: int = 5,
            *, skip_to_populated: str | None = None
            ) -> list[dict[str, Any]]:
    """``n`` real rows, with identity-bearing values withheld.

    With ``skip_to_populated`` the first batch in which that column is
    non-null is used instead of the first batch at all. D19 is why: its file
    opens with the compliance-only configuration, whose energy columns are
    null by design, so the literal first five rows of the file show a correct
    dataset and illustrate nothing. Both samples are shown on the page and
    each says which it is.
    """
    import pyarrow.parquet as pq

    if not parts:
        return []
    pf = pq.ParquetFile(parts[0])
    tab: dict[str, Any] | None = None
    if skip_to_populated:
        for batch in pf.iter_batches(batch_size=4096):
            d = batch.to_pydict()
            col = d.get(skip_to_populated)
            if not col:
                break
            idx = next((i for i, v in enumerate(col) if v is not None), None)
            if idx is not None:
                tab = {k: v[idx:idx + n] for k, v in d.items()}
                break
        if tab is None:
            return []
    else:
        tab = next(pf.iter_batches(batch_size=n)).to_pydict()
    hidden = {
        c.name for c in cols
        if any(p in c.name.lower() for p in IDENTITY_PATTERNS)
    }
    out = []
    for i in range(min(n, len(next(iter(tab.values()), [])))):
        row: dict[str, Any] = {}
        for k, v in tab.items():
            if k in hidden:
                row[k] = "withheld"
                continue
            cell = v[i]
            if isinstance(cell, dict):
                # A struct column: flattened to the same leaf names the
                # schema table uses, so the two tables can be read together.
                for ck, cv in cell.items():
                    row[f"{k}.{ck}"] = cv
            else:
                row[k] = cell
        out.append(row)
    # Every sampled row must offer the same columns, or the table is ragged:
    # a struct that is null in one row and populated in the next yields
    # different keys.
    allk: list[str] = []
    for r in out:
        for k in r:
            if k not in allk:
                allk.append(k)
    return [{k: r.get(k) for k in allk} for r in out]


def _json_sample(rows: list[Any], n: int = 5) -> list[dict[str, Any]]:
    """Five rows of a dataset that lives inside a JSON artefact.

    A partial dataset is still on disk, in a file, so it can show real rows
    like any other. Values are stringified and identity-bearing keys withheld
    by the same rule the Parquet sampler uses.
    """
    out: list[dict[str, Any]] = []
    for r in rows[:n]:
        if not isinstance(r, dict):
            out.append({"value": r})
            continue
        row = {}
        for k, v in r.items():
            if any(pat in k.lower() for pat in IDENTITY_PATTERNS):
                row[k] = "withheld"
            elif isinstance(v, (list, dict)):
                row[k] = json.dumps(v, default=str)
            else:
                row[k] = v
        out.append(row)
    allk: list[str] = []
    for r in out:
        for k in r:
            if k not in allk:
                allk.append(k)
    return [{k: r.get(k) for k in allk} for r in out]


#: Keys in a JSON-held dataset that carry a date or a day index.
JSON_DATE_KEYS = re.compile(
    r"(date|_day$|_at$|onset|effective|decided|ts$)", re.I)


def _json_span(rows: list[Any]) -> str:
    """The span of whatever date-like key a JSON-held dataset carries."""
    best: tuple[str, Any, Any] | None = None
    for r in rows:
        if not isinstance(r, dict):
            return "—"
        for k, v in r.items():
            if v is None or not JSON_DATE_KEYS.search(k):
                continue
            if not isinstance(v, (str, int, float)):
                continue
            if best is None or best[0] != k:
                if best is None:
                    best = (k, v, v)
                continue
            lo, hi = best[1], best[2]
            best = (k, min(lo, v), max(hi, v))
    if best is None:
        return "—"
    kind = (" (day index from the run's first day, not a date)"
            if isinstance(best[1], (int, float)) else "")
    return f"`{best[0]}` {best[1]} → {best[2]}{kind}"


#: The runs whose packages live under ``v1/``. The top level is the delivered
#: estate-year; each immediate subdirectory is another run's package, written
#: by the export layer with the same part-and-manifest convention.
#:
#: Added because v1/ stopped holding one run. It now holds three, and a scan
#: of only the top level reported D03, D09 and D20 as missing the moment they
#: were moved into the run they actually describe (I-091) - the data had not
#: gone anywhere, the scan had stopped looking. A catalogue that counts only
#: one run cannot describe this release.
ESTATE_RUN = "estate_year"


def _run_presence(root: Path) -> dict[str, dict[str, dict[str, int]]]:
    """``{dataset: {run: {parts, rows, bytes}}}`` over every run under v1/."""
    import pyarrow.parquet as pq

    out: dict[str, dict[str, dict[str, int]]] = {}
    v1 = root / "v1"
    for pkg in ("observable", "ground_truth", "evidence"):
        base = v1 / pkg
        if not base.exists():
            continue
        places = [(ESTATE_RUN, base)] + [
            (d.name, d) for d in sorted(base.iterdir()) if d.is_dir()]
        for run, place in places:
            for f in sorted(place.glob("D*_part*.parquet")):
                ds = f.name.split("_part")[0]
                rec = out.setdefault(ds, {}).setdefault(
                    run, {"parts": 0, "rows": 0, "bytes": 0})
                rec["parts"] += 1
                rec["bytes"] += f.stat().st_size
                try:
                    rec["rows"] += pq.ParquetFile(f).metadata.num_rows
                except Exception:
                    pass
    return out


def _evidence_rows(root: Path) -> dict[str, list[dict[str, Any]]]:
    """Datasets whose rows live in an evidence artefact rather than a part."""
    found: dict[str, list[dict[str, Any]]] = {}
    ev = root / "v1" / "evidence"
    for path in sorted(ev.glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        def walk(obj: Any) -> None:
            if not isinstance(obj, dict):
                return
            for k, v in obj.items():
                m = EVIDENCE_ROW_KEY.match(k)
                if m and isinstance(v, list):
                    ds = f"D{m.group(1)}"
                    found.setdefault(ds, []).append({
                        "artefact": f"v1/evidence/{path.name}",
                        "key": k, "rows": len(v),
                        "columns": sorted(v[0]) if v and isinstance(v[0], dict)
                        else [],
                        "sample": _json_sample(v),
                        "span": _json_span(v),
                    })
                walk(v)

        walk(doc)
        # A dataset can also BE an artefact: D24 declares itself.
        if isinstance(doc, dict) and isinstance(doc.get("dataset"), str):
            ds = doc["dataset"].strip().upper()
            if re.fullmatch(r"D\d{2}", ds):
                rows = doc.get("n_targets") or doc.get("n_rows")
                # The list of RECORDS, not merely the first list in the
                # document: d24's artefact carries `exposures_present`, a
                # list of strings, before `targets`, and taking the first
                # list made every declared column of D24 read as absent.
                target_list = next(
                    (v for v in doc.values()
                     if isinstance(v, list) and v and isinstance(v[0], dict)),
                    [])
                found.setdefault(ds, []).append({
                    "artefact": f"v1/evidence/{path.name}",
                    "key": "(the artefact is the dataset)",
                    "rows": int(rows) if isinstance(rows, int)
                    else len(target_list),
                    "columns": sorted(target_list[0])
                    if target_list and isinstance(target_list[0], dict) else [],
                    "sample": _json_sample(target_list),
                    "span": _json_span(target_list),
                })
    return found


def _plausibility_links(root: Path) -> dict[str, list[dict[str, Any]]]:
    """Checks that name a dataset in their own record.

    Attribution by the artefact's own text, rather than by a mapping written
    here: a hand-kept list of which check reads which dataset is exactly the
    kind of list that goes stale, and the method is stated on the page so a
    reader can see how the link was made.
    """
    out: dict[str, list[dict[str, Any]]] = {}
    path = root / "v1" / "evidence" / "plausibility.json"
    if not path.exists():
        return out
    doc = json.loads(path.read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []
    for v in doc.values():
        if isinstance(v, list) and v and isinstance(v[0], dict) \
                and "check_id" in v[0]:
            checks.extend(v)
    for fam in (doc.get("families") or {}).values() if isinstance(
            doc.get("families"), dict) else []:
        if isinstance(fam, list):
            checks.extend(c for c in fam if isinstance(c, dict)
                          and "check_id" in c)
    seen = set()
    for c in checks:
        cid = c.get("check_id")
        if cid in seen:
            continue
        seen.add(cid)
        blob = json.dumps(c, default=str)
        for ds in set(re.findall(r"\bD(\d{2})\b", blob)):
            out.setdefault(f"D{ds}", []).append({
                "check_id": cid,
                "quantity": c.get("quantity", ""),
                "outcome": c.get("outcome", ""),
                "exposure": c.get("source_exposure") or (
                    "none" if c.get("sourced") else "unsourced"),
                "source_key": c.get("source_key") or "—",
            })
    return out


def _code_reads(root: Path) -> dict[str, list[str]]:
    """Where the plausibility code opens a dataset, as file and line."""
    out: dict[str, list[str]] = {}
    base = root / "scripts" / "baile_nua"
    for path in sorted(base.rglob("*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            for m in re.finditer(r"""(?:pkg|package)\.get\(\s*["'](D\d{2})["']""",
                                 line):
                rel = path.relative_to(root).as_posix()
                out.setdefault(m.group(1), []).append(f"{rel}:{i}")
    return out


def _invariant_links(root: Path) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    path = root / "v1" / "evidence" / "v0_invariants.json"
    if not path.exists():
        return out
    doc = json.loads(path.read_text(encoding="utf-8"))
    for inv in doc.get("invariants", []):
        blob = json.dumps(inv, default=str)
        for ds in set(re.findall(r"\bD(\d{2})\b", blob)):
            out.setdefault(f"D{ds}", []).append({
                "invariant": inv.get("invariant", ""),
                "status": inv.get("status", ""),
                "n_checked": inv.get("n_checked", 0),
                "n_violations": inv.get("n_violations", 0),
            })
    return out


def _git_head(root: Path) -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
            text=True, check=True).stdout.strip()
    except Exception:                                          # pragma: no cover
        return "unknown"


def _dir_bytes(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def _human(n: int) -> str:
    x = float(n)
    for unit in ("B", "kB", "MB", "GB", "TB"):
        if x < 1024 or unit == "TB":
            return f"{x:.1f} {unit}" if unit != "B" else f"{int(x)} B"
        x /= 1024
    return f"{x:.1f} TB"                                        # pragma: no cover


# --------------------------------------------------------------------------- #
# assembly
# --------------------------------------------------------------------------- #

def build_catalogue(*, project_root: Path) -> dict[str, Any]:
    """Every fact the document states, collected from disk."""
    import yaml

    root = Path(project_root)
    spec = yaml.safe_load(
        (root / "scripts" / "baile_nua" / "schema" / "datasets.yaml")
        .read_text(encoding="utf-8"))
    declared = spec["datasets"]

    from baile_nua.release import packages as pkg_mod

    v1 = root / "v1"
    elsewhere = _evidence_rows(root)
    presence = _run_presence(root)
    checks = _plausibility_links(root)
    reads = _code_reads(root)
    invs = _invariant_links(root)

    not_shipped: dict[str, str] = {}
    dp = v1 / "evidence" / "delivery_packages.json"
    if dp.exists():
        reasons = (json.loads(dp.read_text(encoding="utf-8"))
                   .get("what_is_not_shipped_and_why") or {})
        for ds, keys in NOT_SHIPPED_KEYS.items():
            for k in keys:
                if k in reasons:
                    not_shipped[ds] = reasons[k]

    facts: dict[str, DiskFacts] = {}
    for ds in sorted(declared):
        f = DiskFacts(dataset_id=ds)
        # `evidence` is included because a META dataset's released form is a
        # Parquet part in the evidence view, not in either data package. D22
        # is the case: the signature library is written there by the export
        # layer, and a scan of only the two data packages reported it missing
        # while it sat on disk.
        #
        # I-104. The top level is tried FIRST, then each run subdirectory, and
        # the search stops at the first hit so the estate-year still wins for a
        # dataset that is in both. Without the fallback this scan disagreed with
        # `_run_presence` above, which has descended into run subdirectories
        # since I-091: a dataset filed under the run it describes was reported
        # `Status | present` by one path and `Path | not present in v1/` by the
        # other, two lines apart, and its Rows, Size, Time span, Schema and
        # Sample all came back empty. It read, verbatim:
        #
        #     **Schema** - not available: the dataset is not on disk in `v1/`.
        #     It is **present**.
        #
        # on D03, D09 and D20 (the I-091 relocations) and then on D17 and
        # D17_aggregate, which only the C2 town run can produce. Every affected
        # dataset was one that exists ONLY under a run subdirectory, which is
        # why no top-level dataset ever showed it.
        for sub in ("observable", "ground_truth", "evidence"):
            places = [(sub, v1 / sub)]
            base = v1 / sub
            if base.exists():
                places += [(f"{sub}/{d.name}", d)
                           for d in sorted(base.iterdir()) if d.is_dir()]
            for label, place in places:
                parts = sorted(place.glob(f"{ds}_part*.parquet"))
                if parts:
                    f.parts = parts
                    f.package_dir = label
                    f.manifests = sorted(
                        place.glob(f"{ds}_part*.manifest.json"))
                    break
            if f.parts:
                break
        if f.parts:
            f.rows, f.n_bytes, f.columns = _scan_dataset(f.parts)
            f.time_span, f.resolution = _span_and_resolution(f.parts, f.columns)
            f.sample = _sample(f.parts, f.columns)
            # If every measure in the first five rows is null, the sample
            # shows nothing about the dataset. Take a second one from the
            # first batch where the principal measure is populated, and keep
            # both: the literal opening rows, and rows that illustrate.
            measure = next(
                (c.name for c in f.columns
                 if c.name in ("import_wh", "energy_wh", "temp_living_c",
                               "value", "reading")), None)
            if measure and f.sample and all(
                    r.get(measure) is None for r in f.sample):
                f.sample_populated = _sample(
                    f.parts, f.columns, skip_to_populated=measure)
                f.sample_populated_column = measure
            if f.manifests:
                f.manifest = json.loads(
                    f.manifests[0].read_text(encoding="utf-8"))
        f.elsewhere = elsewhere.get(ds, [])
        f.other_runs = {r: v for r, v in presence.get(ds, {}).items()
                        if r != ESTATE_RUN}
        facts[ds] = f

    # headline figures, every one from a file
    run = json.loads((v1 / "run_diagnostics.json").read_text(encoding="utf-8"))
    wp5_path = v1 / "evidence" / "wp5_tenyear.json"
    wp5 = (json.loads(wp5_path.read_text(encoding="utf-8"))
           if wp5_path.exists() else {})
    town_candidates = sorted(
        (root / "work").glob("town*/town_diagnostics.json"),
        key=lambda p: p.stat().st_mtime, reverse=True)
    town = (json.loads(town_candidates[0].read_text(encoding="utf-8"))
            if town_candidates else {})

    # The schema file declares a design revision; the docs folder holds the
    # design documents. They can disagree, and here they do, so both are
    # reported rather than one being presented as the revision.
    design_docs = sorted(
        (root / "docs").glob("Baile_Nua_Technical_Design_Review_r*.md"))
    newest_doc = design_docs[-1].name if design_docs else None
    doc_rev = None
    if newest_doc:
        import re as _re
        m = _re.search(r"_r(\d+)\.md$", newest_doc)
        doc_rev = int(m.group(1)) if m else None

    n_present = sum(1 for f in facts.values() if f.status == "present")
    n_partial = sum(1 for f in facts.values() if f.status == "partial")
    n_missing = sum(1 for f in facts.values() if f.status == "missing")

    return {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "git_head": _git_head(root),
        "project_root": str(root),
        "schema_version": spec["schema_version"],
        "design_revision": spec["design_revision"],
        "newest_design_doc": newest_doc,
        "design_doc_revision": doc_rev,
        "design_revision_mismatch": bool(
            doc_rev is not None and doc_rev != spec["design_revision"]),
        "label": spec["label"],
        "units": spec["units"],
        "id_prefixes": spec["id_prefixes"],
        "access_classes": spec["access_classes"],
        "declared": declared,
        "facts": facts,
        "checks": checks,
        "code_reads": reads,
        "invariants": invs,
        "not_shipped": not_shipped,
        "packages": {
            "observable": list(pkg_mod.OBSERVABLE_DATASETS),
            "observable_views_of_gt": dict(pkg_mod.OBSERVABLE_VIEWS_OF_GT),
            "ground_truth": list(pkg_mod.GROUND_TRUTH_DATASETS),
            "descriptions": {k: v["receives"] for k, v in
                             pkg_mod.PACKAGES.items()},
        },
        "run": run,
        "wp5": wp5,
        "town": town,
        "v1_bytes": _dir_bytes(v1),
        "v1_dirs": {
            p.name: _dir_bytes(p) for p in sorted(v1.iterdir()) if p.is_dir()
        },
        "v1_files": {
            p.name: p.stat().st_size for p in sorted(v1.iterdir())
            if p.is_file()
        },
        "run_presence": presence,
        "runs": sorted({r for v in presence.values() for r in v}),
        "counts": {"present": n_present, "partial": n_partial,
                   "missing": n_missing, "declared": len(declared),
                   "present_in_any_run": len(presence),
                   "by_run": {
                       r: sum(1 for v in presence.values() if r in v)
                       for r in sorted({r for v in presence.values()
                                        for r in v})}},
    }


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #

def _md_cell(v: Any, width: int = 46) -> str:
    if v is None:
        return "—"
    s = str(v)
    s = s.replace("|", "\\|").replace("\n", " ")
    return s if len(s) <= width else s[: width - 1] + "…"


def _package_of(ds: str, cat: dict[str, Any]) -> str:
    d = cat["declared"][ds]
    cls = d["access_class"]
    if cls == "OBS":
        return "Observable"
    if cls == "META":
        return "Evidence"
    if ds in cat["packages"]["observable_views_of_gt"]:
        return "Ground truth (+ observable view)"
    return "Ground truth"


def render(cat: dict[str, Any]) -> str:
    L: list[str] = []
    w = L.append
    facts: dict[str, DiskFacts] = cat["facts"]
    declared = cat["declared"]
    run, wp5, town = cat["run"], cat["wp5"], cat["town"]

    # ---------------- cover ------------------------------------------------
    w("# Baile Nua: HRSD_Occupants Dataset Catalogue")
    w("")
    w("### Synthetic occupants of an Irish town, calibrated to Cobh")
    w("")
    w(f"**{cat['label']}**")
    w("")
    w("> **v1 candidate. Not a release. Do not use for published results.**")
    w("")
    w("| | |")
    w("|---|---|")
    w("| Version | v1 candidate |")
    w(f"| Generated | {cat['generated_at']} |")
    w(f"| Git HEAD | `{cat['git_head']}` |")
    w(f"| Schema version | {cat['schema_version']} |")
    w(f"| Design revision | {cat['design_revision']}, as the schema file "
      f"declares it"
      + (f" — the newest design document on disk is "
         f"`{cat['newest_design_doc']}` (see Appendix D.6)"
         if cat.get("design_revision_mismatch") else "") + " |")
    w("")
    w("### Headline figures")
    w("")
    w("| | | from |")
    w("|---|---|---|")
    sl = run.get("slice", {})
    if town:
        tsl = town.get("slice", {})
        w(f"| Town residents | {tsl.get('n_people', '—'):,} | "
          f"`work/town*/town_diagnostics.json` |"
          if isinstance(tsl.get("n_people"), int) else
          f"| Town residents | — | `work/town*/town_diagnostics.json` |")
        w(f"| Town homes | {tsl.get('n_homes', '—'):,} | "
          f"`work/town*/town_diagnostics.json` |"
          if isinstance(tsl.get("n_homes"), int) else
          f"| Town homes | — | `work/town*/town_diagnostics.json` |")
    w(f"| Residents in this package | {sl.get('n_people', '—')} | "
      f"`v1/run_diagnostics.json` |")
    w(f"| Homes in this package | {sl.get('n_homes', '—')} | "
      f"`v1/run_diagnostics.json` |")
    if wp5:
        w(f"| Years covered, life course | {wp5.get('span', '—')} "
          f"({wp5.get('n_years_simulated', '—')} years) | "
          f"`v1/evidence/wp5_tenyear.json` |")
    # Derived, not stated: the earliest and latest timestamp over every
    # present dataset. The first version of this line carried the year as a
    # literal, which is exactly the kind of figure this document is not
    # allowed to contain.
    stamps: list[tuple[Any, str, str]] = []
    for ds0, f in facts.items():
        for c in f.columns:
            if c.name.rsplit(".", 1)[-1] not in TIME_COLUMNS:
                continue
            for v in (c.minimum, c.maximum):
                if getattr(v, "year", None) is not None:
                    stamps.append((v, ds0, c.name))
    if stamps:
        lo = min(stamps, key=lambda x: x[0])
        hi = max(stamps, key=lambda x: x[0])
        note = (f"timestamp statistics of every present dataset; the latest "
                f"is `{hi[1]}.{hi[2]}`")
        if hi[0].year != lo[0].year:
            note += (f", which carries past the simulated year because the "
                     f"device clock error in {hi[1]} is modelled rather than "
                     f"corrected")
        w(f"| Time coverage, this package | {lo[0]} → {hi[0]} | {note} |")
    else:
        w("| Time coverage, this package | — | no timestamp column on disk |")
    c = cat["counts"]
    w(f"| Datasets declared | {c['declared']} | `schema/datasets.yaml` |")
    w(f"| Datasets present in v1, any run | "
      f"{c['present_in_any_run']} | Parquet parts on disk |")
    for r, n in c["by_run"].items():
        label = ("the delivered estate-year" if r == ESTATE_RUN
                 else f"the `{r}` run")
        w(f"| — of which in {label} | {n} | `v1/*/"
          + ("" if r == ESTATE_RUN else f"{r}/") + "` |")
    w(f"| Datasets partial | {c['partial']} | rows in an evidence artefact |")
    w(f"| Datasets missing from v1 | {c['missing']} | absence on disk |")
    w(f"| Total size of `v1/` | {_human(cat['v1_bytes'])} | `stat()` |")
    w("")
    w("> **The `town14` run's engine-streamed datasets are not in `v1/`.** The "
      "C2 14-day full-town run writes D10, D11, D13, D16, D17, D19 and "
      "D17_aggregate, and only D17 and D17_aggregate are filed here — they are "
      "the two datasets no other run can produce, because the estate-year is "
      "C1 and D17 reads a solved power flow. The other five stay in the run "
      "root, at **`work/town4/pkg/{ground_truth,observable}/`**, where the run "
      "wrote them; D10, D11, D13, D16 and D19 are listed present above on the "
      "strength of the estate-year\'s own copies, which are a different slice "
      "at a different seed. Anyone wanting the town\'s 1,092-home versions "
      "should read the run root, not this package.")
    w("")
    w("### The three delivery packages")
    w("")
    w("| Package | Who it is for |")
    w("|---|---|")
    for name, label in (("observable", "**Observable view**"),
                        ("ground_truth", "**Ground-truth view**"),
                        ("evidence", "**Evidence view**")):
        w(f"| {label} | {cat['packages']['descriptions'].get(name, '—')} |")
    w("")
    w("Every figure in this document is read from the files it names. The "
      "per-dataset descriptions draw on design revision 4; every factual "
      "claim beside them is checked against disk, and where there is no "
      "artefact there is no number.")
    w("")
    w(PAGE_BREAK)
    w("")

    # ---------------- contents --------------------------------------------
    w("## Contents")
    w("")
    groups = {
        "Observable": [], "Ground truth": [],
        "Ground truth (+ observable view)": [], "Evidence": [],
    }
    for ds in sorted(declared):
        groups[_package_of(ds, cat)].append(ds)
    for group in ("Observable", "Ground truth (+ observable view)",
                  "Ground truth", "Evidence"):
        ids = groups[group]
        if not ids:
            continue
        w(f"### {group}")
        w("")
        w("| Dataset | Title | Class | Status |")
        w("|---|---|---|---|")
        for ds in ids:
            d, f = declared[ds], facts[ds]
            w(f"| [{ds}](#{ds.lower()}) | {d['title']} | "
              f"{d['access_class']} | {f.status} |")
        w("")
    w("### Appendices")
    w("")
    for anchor, title in (
            ("appendix-a", "A. Folder tree of `v1/`"),
            ("appendix-b", "B. Keys and joins"),
            ("appendix-c", "C. Conventions"),
            ("appendix-d", "D. Design against disk"),
            ("appendix-e", "E. Glossary")):
        w(f"- [{title}](#{anchor})")
    w("")
    w(PAGE_BREAK)
    w("")

    # ---------------- one page per dataset --------------------------------
    for ds in sorted(declared):
        d, f = declared[ds], facts[ds]
        prose = PROSE.get(ds, {})
        w(f'<a id="{ds.lower()}"></a>')
        w("")
        w(f"## {ds} · {d['title']}")
        w("")
        w(prose.get("description", "_No description written._"))
        w("")
        w("**Key points**")
        w("")
        for p in prose.get("points", []):
            w(f"- {p}")
        w("")
        w("**Facts**")
        w("")
        w("| | |")
        w("|---|---|")
        w(f"| Class | {d['access_class']} — "
          f"{cat['access_classes'][d['access_class']]['description']} |")
        w(f"| Package | {_package_of(ds, cat)} |")
        if f.parts:
            w(f"| Path | `v1/{f.package_dir}/{ds}_part*.parquet` "
              f"({len(f.parts)} part"
              f"{'s' if len(f.parts) != 1 else ''}) |")
        elif f.elsewhere:
            w(f"| Path | {', '.join('`' + e['artefact'] + '`' for e in f.elsewhere)} |")
        else:
            w("| Path | not present in `v1/` |")
        w(f"| Format | declared `{d.get('storage', '—')}`"
          + (" ; on disk Parquet" if f.parts else "") + " |")
        part_by = d.get("partition_by")
        w(f"| Partitioning | "
          f"{('by ' + ', '.join(part_by)) if part_by else 'none declared'}"
          + (f" ; on disk {len(f.parts)} sequential parts" if f.parts else "")
          + " |")
        w(f"| Rows | {f.rows:,} |" if f.parts else
          (f"| Rows | {sum(e['rows'] for e in f.elsewhere):,} "
           f"(in an evidence artefact) |" if f.elsewhere else "| Rows | — |"))
        w(f"| Size | {_human(f.n_bytes)} |" if f.parts else "| Size | — |")
        span = f.time_span
        if span == "—" and f.elsewhere:
            span = next((e.get("span") for e in f.elsewhere
                         if e.get("span") and e["span"] != "—"), "—")
        w(f"| Time span | {span} |")
        w(f"| Resolution | {f.resolution if f.parts else d.get('grain', '—')} |")
        key = d.get("keyed_by")
        idcols = [c.name for c in f.columns
                  if c.name.endswith("_id") or c.name == "ts"]
        w(f"| Primary key | "
          + (f"declared `keyed_by: {key}`" if key else f"grain `{d['grain']}`")
          + (f" ; id columns on disk: "
             f"{', '.join('`' + c + '`' for c in idcols)}" if idcols else "")
          + " |")
        runs = cat["run_presence"].get(ds, {})
        if runs:
            w("| Present for | "
              + "; ".join(
                  f"{'estate-year' if r == ESTATE_RUN else r} "
                  f"({v['rows']:,} rows, {_human(v['bytes'])})"
                  for r, v in runs.items())
              + " |")
        w(f"| Status | **{f.status}**"
          + (f" — {cat['not_shipped'][ds]}" if ds in cat["not_shipped"] else "")
          + " |")
        if f.manifest:
            w(f"| Leakage audit | {f.manifest.get('leakage_audit', '—')} |")
            w(f"| Part hash | `{f.manifest.get('file_sha256', '—')[:16]}…` "
              f"(part 0) |")
        w("")

        # schema
        if f.parts:
            w("**Schema** — types, null counts and ranges from the Parquet "
              "footers; descriptions and units from `schema/datasets.yaml`.")
            w("")
            decl = {x["name"]: x for x in d["fields"]}
            w("| Column | Type | Unit | Nulls | Min | Max | Declared |")
            w("|---|---|---|---|---|---|---|")
            for c in f.columns:
                top = c.name.split(".", 1)[0]
                dd = decl.get(top, {})
                unit = dd.get("unit")
                if not unit:
                    der = _derived_unit(c.name, cat["units"])
                    unit = f"{der} *(derived)*" if der else "—"
                if top not in decl:
                    tag = "**not in schema**"
                elif "." in c.name:
                    tag = f"leaf of `{top}`"
                else:
                    tag = "required" if dd.get("required") else "optional"
                w(f"| `{c.name}` | {_md_cell(c.logical_type, 24)} | {unit} | "
                  f"{c.nullable_in_practice} | {_md_cell(c.minimum, 26)} | "
                  f"{_md_cell(c.maximum, 26)} | {tag} |")
            w("")
            on_disk_top = {c.name.split(".", 1)[0] for c in f.columns}
            miss = [x["name"] for x in d["fields"]
                    if x["name"] not in on_disk_top]
            if miss:
                w(f"Declared but absent from the file: "
                  f"{', '.join('`' + m + '`' for m in miss)}. See Appendix D.")
                w("")
            if any("." in c.name for c in f.columns):
                w("A dotted name is a leaf of a struct column: the Parquet "
                  "footer flattens a struct, so the file physically carries "
                  "the leaves while the dataset logically carries the parent.")
                w("")
            descs = [(x["name"], x.get("notes") or x.get("mechanism"))
                     for x in d["fields"]
                     if (x.get("notes") or x.get("mechanism"))]
            if descs:
                w("<details><summary>Column descriptions, as declared"
                  "</summary>")
                w("")
                w("| Column | Declared description |")
                w("|---|---|")
                for n, t in descs:
                    w(f"| `{n}` | {_md_cell(t, 150)} |")
                w("")
                w("</details>")
                w("")
        else:
            w("**Schema** — not available: the dataset is not on disk in "
              f"`v1/`. It is **{f.status}**.")
            w("")
            if f.elsewhere:
                w("Rows exist outside the released packages:")
                w("")
                w("| Artefact | Key | Rows | Columns |")
                w("|---|---|---|---|")
                for e in f.elsewhere:
                    w(f"| `{e['artefact']}` | `{e['key']}` | {e['rows']:,} | "
                      f"{_md_cell(', '.join(e['columns']), 70)} |")
                w("")
            if ds in cat["not_shipped"]:
                w(f"Reason recorded on disk, in "
                  f"`v1/evidence/delivery_packages.json`: "
                  f"*{cat['not_shipped'][ds]}*")
                w("")
            w(f"The declared schema has {len(d['fields'])} fields: "
              + ", ".join(f"`{x['name']}`" for x in d["fields"]) + ".")
            w("")

        # sample
        if f.sample:
            w("**Sample** — the first five rows of part 0, as written. "
              "Identity-bearing columns would be withheld; this dataset "
              "carries none.")
            w("")
            cols = list(f.sample[0])
            w("| " + " | ".join(f"`{c}`" for c in cols) + " |")
            w("|" + "---|" * len(cols))
            for r in f.sample:
                w("| " + " | ".join(_md_cell(r[c], 24) for c in cols) + " |")
            w("")
        elif any(e.get("sample") for e in f.elsewhere):
            e = next(e for e in f.elsewhere if e.get("sample"))
            w(f"**Sample** — five rows as they are held in "
              f"`{e['artefact']}`. The dataset has no released Parquet part, "
              f"so these are the rows there are.")
            w("")
            cols = list(e["sample"][0])
            w("| " + " | ".join(f"`{c}`" for c in cols) + " |")
            w("|" + "---|" * len(cols))
            for r in e["sample"]:
                w("| " + " | ".join(_md_cell(r[c], 22) for c in cols) + " |")
            w("")
        else:
            w("**Sample** — none: no rows on disk in `v1/`.")
            w("")
        if f.sample_populated:
            w(f"The rows above are the literal first five, and every measure "
              f"in them is null — correct, and uninformative. The first five "
              f"rows in which `{f.sample_populated_column}` is populated:")
            w("")
            cols = list(f.sample_populated[0])
            w("| " + " | ".join(f"`{c}`" for c in cols) + " |")
            w("|" + "---|" * len(cols))
            for r in f.sample_populated:
                w("| " + " | ".join(_md_cell(r[c], 20) for c in cols) + " |")
            w("")

        # links
        w("**Joins**")
        w("")
        joins = []
        artefact_cols = [
            ColumnFacts(name=n, physical_type="", logical_type="", nulls=0,
                        rows=0)
            for e in f.elsewhere for n in e["columns"]
        ]
        for c in (f.columns or artefact_cols):
            if c.name == "premises_id":
                joins.append("`premises_id` → D18, D19, D27 to D30 "
                             "(the meter-boundary identity of a home)")
            elif c.name == "building_id":
                joins.append("`building_id` → D02 fabric, D03 passport, "
                             "D16 state, D01 geography")
            elif c.name == "household_id":
                joins.append("`household_id` → D06 membership, D04 assets")
            elif c.name == "person_id":
                joins.append("`person_id` → D05 persons, D08 states, "
                             "D09 events, D10 activities")
            elif c.name == "signature_id":
                joins.append("`signature_id` → D22 signature library")
        if ds in cat["packages"]["observable_views_of_gt"]:
            joins.append(
                f"**Masked view:** this dataset is ground truth with an "
                f"observable view — "
                f"{cat['packages']['observable_views_of_gt'][ds]}")
        obs_view = d.get("obs_view")
        if obs_view:
            joins.append(f"Declared observable view: `{obs_view}`")
        gtc = [(x["name"], x["gt_counterpart"]) for x in d["fields"]
               if x.get("gt_counterpart")]
        for n, g in gtc:
            joins.append(f"`{n}` observes `{g}` — agreement with it must not "
                         f"exceed the error model's bound")
        if not joins:
            joins.append("No join keys present on disk for this dataset.")
        for j in sorted(set(joins)):
            w(f"- {j}")
        w("")

        # validation
        w("**Validation**")
        w("")
        ck = cat["checks"].get(ds, [])
        iv = cat["invariants"].get(ds, [])
        rd = cat["code_reads"].get(ds, [])
        if ck:
            w("Plausibility checks whose own record in "
              "`v1/evidence/plausibility.json` names this dataset:")
            w("")
            w("| Check | Quantity | Exposure | Outcome |")
            w("|---|---|---|---|")
            for c0 in sorted(ck, key=lambda x: str(x["check_id"]))[:12]:
                w(f"| {c0['check_id']} | {_md_cell(c0['quantity'], 52)} | "
                  f"{c0['exposure']} | **{c0['outcome']}** |")
            w("")
        if iv:
            w("V0 invariants naming this dataset, from "
              "`v1/evidence/v0_invariants.json`:")
            w("")
            w("| Invariant | Checked | Violations | Status |")
            w("|---|---|---|---|")
            for i0 in iv:
                w(f"| {i0['invariant']} | {i0['n_checked']:,} | "
                  f"{i0['n_violations']} | **{i0['status']}** |")
            w("")
        if rd:
            w(f"Opened directly by: "
              + ", ".join(f"`{x}`" for x in sorted(set(rd))[:6]) + ".")
            w("")
        if not (ck or iv or rd):
            w("No check in the artefacts names this dataset, and no module "
              "opens it by name. That is a statement about the evidence on "
              "disk, not a claim that the dataset is unchecked.")
            w("")
        w("Links are attributed from the artefacts themselves — a check is "
          "listed where its own record names the dataset — rather than from a "
          "mapping kept in the generator, which would go stale.")
        w("")
        w(PAGE_BREAK)
        w("")

    # ---------------- appendices ------------------------------------------
    w('<a id="appendix-a"></a>')
    w("")
    w("## Appendix A · Folder tree of `v1/`")
    w("")
    w("Folder sizes from `stat()` over every file beneath them. Within a "
      "folder, files are grouped by name pattern — a part number collapses "
      "to `*` — and the groups are listed largest first.")
    w("")
    w("```")
    w(f"v1/   {_human(cat['v1_bytes']):>12}   total")
    dirs = list(cat["v1_dirs"].items())
    files = list(cat["v1_files"].items())
    for di, (name, n) in enumerate(dirs):
        last_dir = (di == len(dirs) - 1) and not files
        w(f"{'└──' if last_dir else '├──'} {name + '/':<22} "
          f"{_human(n):>10}")
        stem = "    " if last_dir else "│   "
        sub = Path(cat["project_root"]) / "v1" / name
        kinds: dict[str, list[int]] = {}
        for q in sorted(sub.iterdir()):
            if q.is_file():
                kinds.setdefault(re.sub(r"_part\d+", "_part*", q.name), []
                                 ).append(q.stat().st_size)
        ranked = sorted(kinds.items(), key=lambda kv: -sum(kv[1]))
        shown = ranked[:8]
        for gi, (k, sizes) in enumerate(shown):
            tail = (gi == len(shown) - 1) and len(ranked) <= 8
            w(f"{stem}{'└──' if tail else '├──'} {k:<30} "
              f"{len(sizes):>3} file(s) {_human(sum(sizes)):>10}")
        if len(ranked) > 8:
            rest = ranked[8:]
            w(f"{stem}└── … {len(rest)} further name pattern(s)      "
              f"{sum(len(s) for _, s in rest):>3} file(s) "
              f"{_human(sum(sum(s) for _, s in rest)):>10}")
    for fi, (name, n) in enumerate(files):
        w(f"{'└──' if fi == len(files) - 1 else '├──'} {name:<22} "
          f"{_human(n):>10}")
    w("```")
    w("")
    w(PAGE_BREAK)
    w("")

    w('<a id="appendix-b"></a>')
    w("")
    w("## Appendix B · Keys and joins")
    w("")
    w("```")
    w("                    small_area  (CSO small-area code, e.g. 047106012)")
    w("                         │")
    w("                         │  every dwelling sits in exactly one")
    w("                         ▼")
    w("  D01 town_geo ──── building_id (B-) ──── D02 fabric ──── D03 passport")
    w("                         │                    │")
    w("                         │                    └──── D04 assets (A-)")
    w("                         │                                 │")
    w("                         │                          signature_id → D22")
    w("                         ▼")
    w("                   household_id (H-) ──── D06 membership ──┐")
    w("                         │                                 │")
    w("                         ▼                                 ▼")
    w("                   person_id (P-) ──── D05 persons    D07 relationships")
    w("                         │")
    w("        ┌────────────────┼────────────────┬──────────────┐")
    w("        ▼                ▼                ▼              ▼")
    w("  D08 states      D10 activities    D11 presence    D12 trips")
    w("        │                │                                │")
    w("        └──── D09 life events ──── D20 change labels      │")
    w("                         │                                │")
    w("                         ▼                                ▼")
    w("                   D13 appliance cycles              vehicle state")
    w("                         │")
    w("                         ▼   the meter boundary: GT becomes OBS")
    w("                   premises_id (MPRN-)")
    w("                         │")
    w("        ┌────────────────┼────────────────┬──────────────┐")
    w("        ▼                ▼                ▼              ▼")
    w("  D18 observations  D19 edge exports  D27 tariffs   D28-D30 records")
    w("")
    w("  timestamp: every series is keyed by a UTC instant. Interval datasets")
    w("  carry interval_start and interval_end; point series carry ts.")
    w("```")
    w("")
    w("The identifier prefixes are declared in the schema: "
      + ", ".join(f"`{v}` {k}" for k, v in cat["id_prefixes"].items()) + ".")
    w("")
    w("`premises_id` is the join that matters most, because it is the line "
      "where ground truth becomes observable. A person has a `person_id`, "
      "lives in a `household_id`, which occupies a `building_id`, which is "
      "metered as a `premises_id`. Everything on the observable side of that "
      "line is keyed by premises and nothing on it is keyed by person — which "
      "is the privacy property the leakage test enforces, not a convention.")
    w("")
    w(PAGE_BREAK)
    w("")

    w('<a id="appendix-c"></a>')
    w("")
    w("## Appendix C · Conventions")
    w("")
    w("| | |")
    w("|---|---|")
    w(f"| Time zone | {cat['units']['time']} |")
    # Both of these are claims about the data, so both are checked against
    # it rather than asserted. The ordinal check in particular: "there is no
    # half-hour number in any dataset" is either true of the files or it is
    # not, and a convention document that states it without looking is how a
    # convention quietly stops holding.
    on_disk_cols = {c.name for f in facts.values() for c in f.columns}
    declared_cols = {x["name"] for d0 in declared.values()
                     for x in d0["fields"]}
    has_pair = ({"interval_start", "interval_end"} <= on_disk_cols)
    ordinal_names = sorted(
        n for n in (on_disk_cols | declared_cols)
        if re.search(r"(half_hour|halfhour|\bhh\b|settlement_period"
                     r"|period_index|period_no|interval_index)", n, re.I))
    w("| Timestamp convention | **Period start.** "
      + ("Verified on disk: interval datasets carry both `interval_start` "
         "and `interval_end`, so the convention is in the data rather than "
         "in this document; a point series' `ts` is the instant of the "
         "reading."
         if has_pair else
         "Not verifiable from the files present: no dataset on disk carries "
         "both `interval_start` and `interval_end`.")
      + " |")
    w("| Half-hour indexing | A settlement interval is identified by its "
      "start instant, not by an ordinal. "
      + ("Checked across every column on disk and every column the schema "
         "declares: no half-hour or settlement-period number exists in "
         "either. An ordinal is ambiguous across a daylight-saving boundary "
         "and a UTC instant is not."
         if not ordinal_names else
         f"But these ordinal-looking columns exist, and this claim does not "
         f"hold as written: {', '.join('`' + n + '`' for n in ordinal_names)}.")
      + " |")
    for k, v in cat["units"].items():
        if k == "time":
            continue
        w(f"| Unit, {k} | `{v}` |")
    w("| Energy against power | Interval datasets carry energy in Wh for the "
      "interval and, separately, the peak and minimum power in W within it. "
      "Dividing the one by the other recovers the mean power and loses the "
      "peak, which is the quantity a network cares about. |")
    w("| Missing data | A value absent by mechanism is **null**, and the "
      "reason is carried in the quality flag and the provenance code on the "
      "same row. A value suppressed by an export configuration is also null, "
      "and typed `float64` rather than object, so the file's schema does not "
      "change when a column happens to be entirely absent. |")
    w("| Zero against null | Zero means measured as zero. Null means not "
      "measured. The distinction is load-bearing: a gas dwelling's heat-pump "
      "electricity is zero by construction, and a meter outage is null. |")
    w("")
    w(PAGE_BREAK)
    w("")

    w('<a id="appendix-d"></a>')
    w("")
    w("## Appendix D · Design against disk")
    w("")
    w("A list, not a plan. Nothing here is fixed by this document.")
    w("")
    w("### D.1 Declared datasets with no released Parquet part in `v1/`")
    w("")
    w("| Dataset | Title | Class | Status | Present for another run? | "
      "Rows found elsewhere | Reason recorded on disk |")
    w("|---|---|---|---|---|---|---|")
    gaps: list[str] = []
    for ds in sorted(declared):
        f = facts[ds]
        if f.parts:
            continue
        gaps.append(ds)
        other = "; ".join(f"{e['artefact']} ({e['rows']:,} rows)"
                          for e in f.elsewhere) or "none"
        other_runs = cat["run_presence"].get(ds, {})
        runs_txt = ("; ".join(f"{r} ({v['rows']:,} rows)"
                              for r, v in other_runs.items())
                    if other_runs else "no")
        w(f"| {ds} | {declared[ds]['title']} | "
          f"{declared[ds]['access_class']} | {f.status} | "
          f"{_md_cell(runs_txt, 40)} | {_md_cell(other, 46)} "
          f"| {_md_cell(cat['not_shipped'].get(ds, '—'), 52)} |")
    w("")
    w("### D.2 Declared columns absent from the rows that exist")
    w("")
    w("Covers present datasets, where the comparison is against the Parquet "
      "schema, and partial ones, where it is against the keys of the rows "
      "held in an evidence artefact.")
    w("")
    col_gaps: list[tuple[str, str, str]] = []
    for ds in sorted(declared):
        f = facts[ds]
        if f.parts:
            have = {c.name.split(".", 1)[0] for c in f.columns}
            where = "Parquet"
        elif f.elsewhere:
            have = {n for e in f.elsewhere for n in e["columns"]}
            where = "artefact rows"
        else:
            continue
        for x in declared[ds]["fields"]:
            if x["name"] not in have:
                col_gaps.append((ds, x["name"], where))
    if col_gaps:
        w("| Dataset | Declared column | Required | Compared against |")
        w("|---|---|---|---|")
        for ds, n, where in col_gaps:
            req = next(x.get("required") for x in declared[ds]["fields"]
                       if x["name"] == n)
            w(f"| {ds} | `{n}` | {'yes' if req else 'no'} | {where} |")
    else:
        w("None.")
    w("")
    w("### D.2b Keys in the artefact rows that the schema does not declare")
    w("")
    extra_json: list[tuple[str, str]] = []
    for ds in sorted(declared):
        f = facts[ds]
        if f.parts or not f.elsewhere:
            continue
        decl = {x["name"] for x in declared[ds]["fields"]}
        for e in f.elsewhere:
            for n in e["columns"]:
                if n not in decl:
                    extra_json.append((ds, n))
    if extra_json:
        w("| Dataset | Key on disk |")
        w("|---|---|")
        for ds, n in sorted(set(extra_json)):
            w(f"| {ds} | `{n}` |")
    else:
        w("None.")
    w("")
    w("### D.3 Columns on disk that the schema does not declare")
    w("")
    extra: list[tuple[str, str, str]] = []
    for ds in sorted(declared):
        f = facts[ds]
        if not f.parts:
            continue
        decl = {x["name"] for x in declared[ds]["fields"]}
        for c in f.columns:
            if c.name.split(".", 1)[0] not in decl:
                extra.append((ds, c.name, c.logical_type))
    if extra:
        w("| Dataset | Column on disk | Type |")
        w("|---|---|---|")
        for ds, n, t in extra:
            w(f"| {ds} | `{n}` | {_md_cell(t, 26)} |")
    else:
        w("None.")
    w("")
    w("### D.4 Declared storage against storage on disk")
    w("")
    w("| Dataset | Declared | On disk |")
    w("|---|---|---|")
    for ds in sorted(declared):
        f, d = facts[ds], declared[ds]
        on = ("Parquet" if f.parts else
              ("JSON inside an evidence artefact" if f.elsewhere else "absent"))
        if str(d.get("storage", "")).lower() != "parquet" or not f.parts:
            w(f"| {ds} | {d.get('storage', '—')} | {on} |")
    w("")
    w("### D.5 Datasets present on disk that the schema does not declare")
    w("")
    on_disk_ids = set()
    for sub in ("observable", "ground_truth", "evidence"):
        p = Path(cat["project_root"]) / "v1" / sub
        if p.exists():
            for q in p.glob("D*_part*.parquet"):
                on_disk_ids.add(q.name.split("_part")[0])
    undeclared = sorted(on_disk_ids - set(declared))
    w("None." if not undeclared else
      "\n".join(f"- `{x}`" for x in undeclared))
    w("")
    w("### D.6 Schema revision against design revision")
    w("")
    if cat.get("design_revision_mismatch"):
        w(f"`schema/datasets.yaml` declares `design_revision: "
          f"{cat['design_revision']}` and `design_frozen` with it, while the "
          f"newest design document on disk is "
          f"`docs/{cat['newest_design_doc']}` — revision "
          f"{cat['design_doc_revision']}. Every dataset manifest written by "
          f"the engine stamps the schema's number, so the parts on disk say "
          f"revision {cat['design_revision']} too. Which of the two is "
          f"authoritative is not recorded anywhere, and this document does "
          f"not decide it.")
    else:
        w(f"The schema and the newest design document agree on revision "
          f"{cat['design_revision']}.")
    w("")
    w(PAGE_BREAK)
    w("")

    w('<a id="appendix-e"></a>')
    w("")
    w("## Appendix E · Glossary")
    w("")
    w("| Term | Meaning |")
    w("|---|---|")
    for k, v in cat["access_classes"].items():
        w(f"| **{k}** | {v['description']} Released in the "
          f"`{v['released_in']}` package. |")
    w("| **T1 to T4** | Two different tier systems share the names. "
      "**Sensor tiers** T1 to T4 rank how well a premises is instrumented, "
      "from a basic meter to research-grade sub-metering, and appear per "
      "premises in the observable data. **Label tiers** T1 to T4 rank how "
      "observable a change in D20 is, so a detector's score can be reported "
      "separately for changes that are easy and hard to see. |")
    w("| **Exposure class** | How a source was used before it was compared "
      "against. `none` — never used to build the model, so a pass against it "
      "is independent evidence. `design` — its information reached the model "
      "through a design choice or a sibling table. `selection` — used to "
      "choose between model variants. `tuning` — a parameter was fitted to "
      "it. A source used to build the model cannot validate it, so the three "
      "pass counts are reported separately and never summed. |")
    w("| **E1 / E2** | The engineering gates. E1 is the eight-criterion "
      "verification of the estate-year: invariants, determinism, negative "
      "controls, marginals, a complete replayed year, the MIMIC tests, the "
      "no-calibration claim, and measured cost. E2 is the seven-criterion "
      "gate at town and decade scale: the full town over ten years, the "
      "coupling-lag contract, scale within hardware, physical consistency, "
      "event coverage, the privacy test, and the non-sensor datasets. |")
    w("| **Fidelity tiers F1 to F3** | How the physics is solved. F1 and F2 "
      "are the resistance-capacitance models used here; F3 is a full "
      "building-energy simulation and is out of scope by E1's own "
      "declaration. |")
    w("| **Coupling modes C1, C2** | C1 runs the households without solving "
      "the network. C2 solves a quasi-static power flow at the coupling "
      "epoch, so the network state exists and the per-epoch cost is real. |")
    w("| **GT, OBS, META** | See above. The distinction is enforced by the "
      "schema and by a leakage test, not by where a file sits. |")
    w("| **Provenance code** | Why a value is what it is — measured, "
      "rendered, imputed, gap-filled, suppressed — carried on the value "
      "rather than inferred from its absence. |")
    w("| **Quality flag** | Whether the value should be trusted, on the same "
      "row as the value. |")
    w("")
    w("---")
    w("")
    w(f"Generated by `scripts/baile_nua/report/datasets_md.py` at "
      f"{cat['generated_at']} from git `{cat['git_head'][:12]}`. "
      f"Read-only on `v1/`.")
    w("")
    return "\n".join(L) + "\n"


def write_markdown(*, project_root: Path, out: Path | None = None) -> Path:
    cat = build_catalogue(project_root=project_root)
    path = out or (Path(project_root) / "DATASETS.md")
    path.write_text(render(cat), encoding="utf-8")
    return path


def main() -> int:
    root = Path(__file__).resolve().parents[3]
    import baile_nua.sources_registry  # noqa: F401  (declares the sources)

    cat = build_catalogue(project_root=root)
    path = root / "DATASETS.md"
    path.write_text(render(cat), encoding="utf-8")
    c = cat["counts"]
    text = path.read_text(encoding="utf-8")
    print(f"wrote {path}")
    print(f"  {text.count(PAGE_BREAK)} page breaks, "
          f"{len(text.splitlines()):,} lines, {_human(len(text.encode()))}")
    print(f"  datasets: {c['present']} present, {c['partial']} partial, "
          f"{c['missing']} missing, of {c['declared']} declared")
    return 0


if __name__ == "__main__":                                     # pragma: no cover
    raise SystemExit(main())
