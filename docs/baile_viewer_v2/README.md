# Baile Nua Data Viewer (PHP 7.3 + AJAX)

Two parts:

1. **`build/figures_build.py`** runs once on the EC2 instance. It reads the v1 release with DuckDB (local Parquet where it still exists, B2 for the rest), reduces each figure to a small JSON file, and writes `index.json` plus one file per figure (about 60 files, a few MB in total). These go to `b2eig:hrsd-occupants/v1/figures/`.
2. **`web/`** goes on ultrasoftware.ie. `index.php` is the tabbed page; `api.php` is the AJAX backend. Each tab loads its figures only when opened. The B2 key stays in a config file on the server; the browser never sees it.

## Tabs and figures

| Tab | Figures |
|---|---|
| Overview | release KPIs; rows per year by dataset; simulation speed; peak memory; U27 check matrix |
| Buildings | dwelling type; BER band; heating fuel; heating control; tenure; construction decade; floor area; mean BER by type |
| People | age and sex; household size; household role; education; chronotype |
| Weather | air temperature day × hour (per year); monthly mean temperature (year × month); monthly irradiation |
| Energy | estate import/export per year; import by month; average load by time of day per season; load duration curve; annual import per home |
| Comfort | living-room temperature by month; winter temperature distribution; CO₂ distribution; heat delivered vs outdoor temperature |
| Appliances | energy by programme; cycle starts by hour (weekday/weekend); flexible and shifted cycles |
| Behaviour | what people are doing by hour, weekday and weekend (four sample weeks) |
| Network | transformer loading p95 by month; top 20 elements by peak loading; voltage distribution |
| Smart meters | home-days by metering era; rows by channel; premises with meter data; reading quality |
| Tariffs | tariff type; supplier; export rate coverage |
| Raw files | browse `v1/`, preview any Parquet part (first 200 rows) or JSON/Markdown file |

Single-year figures use `--profile-year` (default 2025, the last full year). Every figure has a **Table** button showing its numbers.

## 1. Build the figures (EC2, via Claude Code)

```
cd ~/hrsd_occupants && mkdir -p viewer && (copy build/figures_build.py here)
pip install --break-system-packages duckdb
set -a; . ~/.b2_hrsd_occupants.env; set +a      # must export B2_KEY_ID and B2_APP_KEY (read key)
python3 viewer/figures_build.py --local-root ~/hrsd_occupants/hrsd/work/replay_2015_2026 \
    --out ~/hrsd_occupants/figures --profile-year 2025 --threads 6 --memory 24GB
rclone copy --checksum ~/hrsd_occupants/figures b2eig:hrsd-occupants/v1/figures/
rclone check ~/hrsd_occupants/figures b2eig:hrsd-occupants/v1/figures/
```

`--only weather,energy` rebuilds selected tabs and keeps the rest of `index.json`. The heaviest tabs (Comfort, Smart meters, Energy) scan hundreds of millions of rows; expect tens of minutes in total.

## 2. Deploy the web part (ultrasoftware.ie)

```
public_html/rd_fusion/            <- index.php, api.php, lib.php
baile_private/config.php          <- outside public_html, from config.sample.php
baile_private/cache/              <- writable by PHP
```

* `lib.php` looks for the config at `../baile_private/config.php` relative to the web folder's parent (`dirname(__DIR__)`). If your layout differs, edit `BAILE_CONFIG` at the top of `lib.php`.
* In `config.php` set the **new** read-only key (bucket hrsd-occupants, prefix `v1/`, List All Bucket Names unticked) and a password hash:
  `php -r "echo password_hash('choose-a-password', PASSWORD_DEFAULT);"`
* PHP extensions needed: `curl`, `simplexml`, `json` (standard on most hosts).
* The bucket CORS rule for `https://ultrasoftware.ie` is only needed for the **Raw files** tab (the browser reads Parquet byte ranges directly). Figures are fetched server-side.
* Alternative to B2 for figures: copy `~/hrsd_occupants/figures/` to the server and set `local_figures_dir` in `config.php`.

## Security

* No key in any browser-visible file. The browser gets presigned URLs valid for 15 minutes, only for keys under `v1/`.
* Sign-in with a single shared password (session cookie, HttpOnly). Leave `password_hash` empty only on a private server.
* All data is labelled `UNVALIDATED SIMULATION EVIDENCE: E1 engineering candidate` and is synthetic.
