"""Collect STRUCTURE.md facts: footers only (schema + column statistics), no row data.
Run inside a subshell that has the B2 env loaded; nothing here prints it."""
import collections, glob, io, json, os, re, struct, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
import pyarrow.parquet as pq

SP = sys.argv[1]
RUN = os.path.expanduser("~/hrsd_occupants/hrsd/work/replay_2015_2026")
B2 = "b2eig:hrsd-occupants/v1"
YEARS = [str(y) for y in range(2015, 2027)]
L = json.load(open(f"{SP}/lsjson.json"))

files = collections.defaultdict(list)  # (year, ds) -> [(path, size)]
for x in L:
    p = x["Path"]
    m = re.match(r"v1/(\d{4})/(\w+)/(\w+?)_part(\d+)\.parquet$", p)
    if m:
        files[(m[1], m[3])].append((p, x["Size"], m[2], int(m[4])))


def tail(path, n):
    r = subprocess.run(["rclone", "cat", "--tail", str(n), f"b2eig:hrsd-occupants/{path}"],
                       capture_output=True, check=True)
    return r.stdout


def footer_meta(year, path):
    local = f"{RUN}/{year}/pkg/" + path.split("/", 2)[2]
    if os.path.exists(local):
        return pq.read_metadata(local), "local"
    t8 = tail(path, 8)
    assert t8[4:] == b"PAR1", path
    n = struct.unpack("<I", t8[:4])[0]
    buf = b"PAR1" + tail(path, n + 8)
    return pq.ParquetFile(io.BytesIO(buf)).metadata, "b2-footer"


def ts_range(md, col):
    lo = hi = None
    idx = md.schema.names.index(col)
    for g in range(md.num_row_groups):
        s = md.row_group(g).column(idx).statistics
        if s is None or not s.has_min_max:
            continue
        lo = s.min if lo is None else min(lo, s.min)
        hi = s.max if hi is None else max(hi, s.max)
    return lo, hi


def job(key):
    year, ds = key
    fl = sorted(files[key], key=lambda t: t[3])
    first, last = fl[0], fl[-1]
    md0, src = footer_meta(year, first[0])
    md1 = md0 if last is first else footer_meta(year, last[0])[0]
    sch = md0.schema.to_arrow_schema()
    tcols = [f.name for f in sch if str(f.type).startswith("timestamp")]
    rng = {}
    for c in tcols[:3]:
        a, _ = ts_range(md0, c); _, b = ts_range(md1, c)
        rng[c] = [str(a), str(b)]
    return key, {
        "schema": [[f.name, str(f.type)] for f in sch], "src": src,
        "parts": len(fl), "bytes": sum(t[1] for t in fl), "category": first[2],
        "row_groups_part0": md0.num_row_groups, "ts": rng,
    }


with ThreadPoolExecutor(8) as ex:
    res = dict(ex.map(job, sorted(files)))

out = collections.defaultdict(dict)
for (y, ds), v in res.items():
    out[ds][y] = v
# manifests (local JSON is kept for every year)
man = collections.defaultdict(dict)
for y in YEARS:
    for m in glob.glob(f"{RUN}/{y}/pkg/*/*_part000.manifest.json"):
        j = json.load(open(m))
        man[j["dataset_id"]][y] = {k: j.get(k) for k in
                                   ("dataset_name", "release_package", "schema_conformance", "streamed",
                                    "unmodelled_fields", "access_class", "calibration_status")}
done = {y: json.load(open(f"{RUN}/{y}/DONE.json")) for y in YEARS}
json.dump({"datasets": out, "manifests": man,
           "rows": {y: done[y]["row_counts"] for y in YEARS}}, open(f"{SP}/facts.json", "w"), indent=1, default=str)
print("datasets", len(out), "jobs", len(res), "b2 footers", sum(v["src"] == "b2-footer" for v in res.values()))
