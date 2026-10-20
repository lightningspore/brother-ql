# Review of brother_ql_next

Reviewed October 19, 2026. Target:
[LunarEclipse363/brother_ql_next](https://github.com/LunarEclipse363/brother_ql_next)
at `9eb7b69eac9778e5a569fd896768c392e5c7c7e7` (main, package 0.12.0).
Compared with SporePrint 1.4a2, whose tested runtime revision is `3eea6fe`.

Keep the SporePrint base and port selected ideas. The most immediate driver gap is
validation of model-specific raster length limits. The other fork also offers
useful network, CLI, documentation, and release practices, but switching wholesale
would drop compatibility and several fixes we already tested on hardware.
The original review changed no library behavior or live deployment.
Follow-up implementation on October 19 added continuous-tape length validation
with resolution scaling, retained stock-specific fixed-label checks, and added
JSON model/label catalogs. See README for the output contract and validation log.
Production still uses the earlier pinned revision until a separate rollout.

## Useful ideas to adopt

| Area | What next provides | Proposed SporePrint work |
| --- | --- | --- |
| Raster length | `add_raster_data` rejects images outside the configured model's minimum/maximum row count. | Highest priority. Add boundary tests for continuous and die-cut stock and account for resolution modes. Reject invalid lengths before sending. Some current synthetic tests use a too-short QL-1110 image and must be corrected. |
| Network addresses | URL parsing, bracketed IPv6, DNS resolution with AF_UNSPEC, and fallback through resolved addresses. | Add IPv4/IPv6/hostname coverage, bounded connect attempts, and guaranteed cleanup. Both live printers currently use USB, so this is less urgent than raster validation. |
| Machine-readable CLI | `info models --json` and `info labels --json`. | Provide stable documented JSON fields, preferably using existing attrs data and standard json rather than adding another runtime serializer dependency. |
| Public API docs | Sphinx reference docs for models, labels, raster generation, replies, and exceptions, published to GitHub Pages. | Document the supported compatibility API and new reply/queue contracts, with examples that distinguish generation from printing. |
| Release process | Changelog, release checklist, PyPI Trusted Publishing, and SPDX package metadata. | Prepare a tested SporePrint release with tag/version checks, clean wheel/source validation, and a PyPI Trusted Publisher. Keep our inherited authorship and license terms; do not copy a different license declaration unexamined. |
| Model/label objects | A smaller manager API with indexing, get/default, identifiers, and label lookup by size. | Useful ergonomics, but keep existing methods and compatibility exports. Avoid changing public `raster.model` from a string to an object without a migration. |

Sources at the reviewed commit:
[raster validation](https://github.com/LunarEclipse363/brother_ql_next/blob/9eb7b69eac9778e5a569fd896768c392e5c7c7e7/brother_ql/raster.py),
[network backend](https://github.com/LunarEclipse363/brother_ql_next/blob/9eb7b69eac9778e5a569fd896768c392e5c7c7e7/brother_ql/backends/network.py),
[CLI](https://github.com/LunarEclipse363/brother_ql_next/blob/9eb7b69eac9778e5a569fd896768c392e5c7c7e7/brother_ql/cli.py),
[release checklist](https://github.com/LunarEclipse363/brother_ql_next/blob/9eb7b69eac9778e5a569fd896768c392e5c7c7e7/CONTRIBUTING.md).

## Isolated checks and confirmed differences

The reviewed source was extracted into a temporary directory and installed in its
own Python 3.13 environment. USB discovery/endpoints and network sockets were
mocked; no physical device was accessed or label printed. Python 3.9.6 was used
separately for the minimum-version converter import check.

| Probe | next 0.12.0 result | SporePrint result or implication |
| --- | --- | --- |
| QL-1110 raster height 300 rows | Raises BrotherQLRasterError; configured minimum is 301. | Accepted: a concrete missing guard. Both accept 301 rows. This checks configured limits, not new physical measurements. |
| Reopen the discovered USB URI | Discovery emits `usb://0x04f9:0x209b_TESTSERIAL`; constructor expects a slash separator and raises ValueError when parsing the product ID. | Our slash-form URI round-trips to the matched mock device. |
| USB read arguments | Calls endpoint read with only length 32. | Our call explicitly passes `timeout=10`. Keep timeout/error behavior already covered by tests. |
| 102 mm stock on QL-800 | `works_with_model('QL-800')` incorrectly returns true. | Ours returns false and permits QL-1110NWB. next checks membership in all known models instead of the label's restriction list. |
| Unknown media byte 0xFE | Returns the numeric value 254 in the media_type field. | Ours returns a readable description and preserves the numeric media_code separately. Both tolerate the unknown value; this is an API-shape difference. |
| Converter import on Python 3.9.6 | TypeError evaluating `str | Image.Image`. Importing the top-level package alone succeeds. | Our converter imports successfully. Their declared Python >=3.9 does not establish converter compatibility. |
| IPv6 URL with simulated first-address failure | Parses the URL and connects using the second resolved address. | Our current parser rejects bracketed IPv6. |
| Failed IPv6 attempt cleanup | First mocked socket was not closed; no connect timeout was configured before the attempt. | Port the approach with cleanup and timeout tests, not the implementation verbatim. |
| `info labels --json` | Valid JSON list with 28 entries. | Our text-only command could gain a stable JSON mode. |

Raw local probe summaries were saved as `/tmp/brother-next-review-results.json`
and `/tmp/brother-sporeprint-review-results.json`; they contain synthetic values.
The code comparison and the commit links above are the durable reference.

## Preserve existing behavior

- Keep strict vendor/product/serial selection, bounded USB reads, short-write
  detection, cleanup, framed replies, and uncertain-send protection.
- Keep hardware-reply fixtures, barcode round-trip tests, and the tested legacy
  `create_label` and `devicedependent` interfaces. next removes those top-level
  compatibility exports and has no corresponding print_queue module.
- Keep InvenTree's device identifiers and P-touch-specific commands. The simpler
  next model definitions are not a drop-in replacement for ours.
- Keep passive status queries for app polling. next's status helper prefixes the
  query with invalidate bytes; importing that behavior would need exclusive USB
  ownership because it clears the command buffer.
- Keep our CI matrix and regression suite. The reviewed tree contains docs and
  publish workflows, but no checked-in test suite or test workflow. That does not
  establish what manual testing its maintainer performs.

## Recommended order

1. Add model-length boundary validation with tests, preserving valid raster bytes.
2. Add stable JSON model/stock output and public usage/API documentation.
3. Prepare PyPI Trusted Publishing as `brother-ql-sporeprint`, the chosen name.
   `brother-ql-next` belongs to the reviewed project. Our wheel and source archive
   passed twine checks. No SporePrint PyPI release has been published; account-side
   publisher configuration has not been verified.
4. Add IPv6 and network connection cleanup/timeouts when pursuing network printing.

The other project has defects that could be useful upstream contributions. No
issues, pull requests, or messages were sent as part of this review.
