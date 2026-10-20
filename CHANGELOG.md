# Changelog

## 1.4.0 — 2026-10-19

First stable SporePrint release, based on the InvenTree Brother QL fork.
Python imports and CLI remain `brother_ql`; distribution name is
`brother-ql-sporeprint`. Do not install multiple Brother QL forks in one environment.

- Strict USB selection, bounded reads, short-write detection, and reliable cleanup.
- Buffered status decoding and queue completion checks with uncertain-send protection.
- Restored legacy label creation and model/label lookup compatibility.
- Continuous-tape length checks with feed-resolution scaling and fixed-label handling.
- JSON model and label catalogs with documented fields.
- Tested Python 3.9 through 3.15, including installed-wheel tests and barcode decoding.

Physical print validation covers QL-800 and QL-1110NWB. Other models retain
inherited support and require their own hardware validation. Durable queues,
inspection acknowledgement, and exclusive printer ownership belong to the application.

## 1.4a2 — 2026-10-19

Initial PyPI alpha upload, superseded by stable 1.4.0.
