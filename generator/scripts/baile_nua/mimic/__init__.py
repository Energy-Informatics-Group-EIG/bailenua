"""HRSD -> MIMIC alignment (design 5.13, 5.14).

Three levels of alignment, per design 5.14:

1. **one trait model** - MIMIC's ten latents are HRSD's native willingness
   traits, same names and scales (:mod:`baile_nua.mimic.crosswalk`);
2. **identical coding** - the export writes MIMIC schema 1.1 fields with
   MIMIC's own value sets (:mod:`baile_nua.mimic.crosswalk`);
3. **the real session process** - participants go through MIMIC's *public API*,
   never straight into the database (:mod:`baile_nua.mimic.runner`).

Safety: the local instance is provisioned by :mod:`baile_nua.mimic.provision`,
which refuses to run against anything but loopback.  See ISSUES.md I-001 - the
MIMIC repo as found would have written to production.
"""
