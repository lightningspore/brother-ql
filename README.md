# Brother QL driver for SporePrint

A separately maintained fork of [matmair/brother_ql-inventree](https://github.com/matmair/brother_ql-inventree),
which derives from [pklaus/brother_ql](https://github.com/pklaus/brother_ql).
The starting point is latest upstream master, `5364d30e0ad088fa943642a05863814390d52b4f`,
including the changes after upstream's `1.4a0` alpha. Original authorship and GPLv3-or-later
licensing are preserved. The upstream InvenTree repository is archived.

The distribution is **`brother-ql-sporeprint`**, development version **1.4a1**.
Python imports remain `brother_ql` and the CLI remains `brother_ql`.
Use a separate virtual environment: this distribution shares import paths with
`brother-ql` and `brother-ql-inventree`, so do not install them together.
No release has been published to PyPI. Both live SporePrint workers now pin this
fork at `5c91577c0ca7e5d8c974e5bb67a3e568512f651f` through their uv lockfile.
The separate application repository owns the deployment and durable queues.

## Improvements in this fork

- USB selection requires vendor, product, and the requested serial descriptor to
  match. It does not silently select another printer with the same product ID.
- USB reads pass an explicit timeout; idle timeouts return empty bytes while real
  transport failures propagate. The legacy `select` strategy uses a bounded USB
  read because USB endpoint objects are not selectable file descriptors.
- Partial writes raise without retry. Initialization errors raise exceptions rather
  than terminating the embedding application. Cleanup is idempotent and attempts
  to restore the kernel driver even if releasing USB resources fails.
- Status decoding retains unknown media/status/phase codes instead of crashing;
  unknown P-touch color codes also remain inspectable. Malformed responses raise
  `ValueError`, matching the existing caller contract.
- `StatusReader` buffers fragmented and coalesced 32-byte replies. Queue waits use
  monotonic deadlines, skip intervening notifications, and reject error packets.
- The print queue requires completion followed by readiness, without requiring an
  observable separate start notification. The first queued page is correctly marked
  as the first page rather than a subsequent page.
- A page is removed before a write begins. A failed or unconfirmed send sets
  `queue.uncertain` and blocks further submission/reset until the caller checks the
  physical label and explicitly calls `clear()`. This discards remaining pages too;
  requeue only what is actually needed. `clear_on_failure=True` does not acknowledge
  uncertainty. Exceptions always release the queue's printing flag.
- Legacy `send()` disposes the transport on success, failure, and early returns.
  `get_status()` accepts fragmented replies and preserves parsing exceptions.
- Raster analysis rejects truncated instructions and honors strict/permissive
  handling of unknown opcodes instead of raising an unexpected assertion.
- The legacy `create_label()` wrapper populates `qlr.data` again. Upstream
  conversion refactoring returned the bytes but discarded them in that wrapper;
  tests now exercise actual raster output for both QL models.
- Queue completion/readiness/status timeouts are configurable (30/3/3 seconds by
  default), and must be finite and positive.
- Packaging uses one authoritative metadata file. Environment diagnostics use
  `importlib.metadata` instead of removed `pkg_resources`. CI tests/builds the fork;
  the inherited automatic upstream PyPI publishing workflow has been removed.

This is not a durable queue: uncertain state lives in memory. Applications must persist
job state across process restarts (SporePrint already does), serialize access to each
physical printer, and avoid automatically replaying jobs after a crash. Use one
`StatusReader` per response stream. It preserves unread packets between calls and
fails closed on malformed framing; it does not guess a new header inside payloads.
Transport reads themselves must be bounded for a reader deadline to be effective.
Queue objects are not thread-safe.

## Development and validation

Python 3.9 or newer is required. From this repository:

```sh
uv venv --python 3.13
uv pip install --python .venv/bin/python -e . build
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m build
.venv/bin/brother_ql --version
.venv/bin/brother_ql info env
```

The hardware-free tests cover USB selection, timeouts, short writes, cleanup,
status-code decoding, reply framing, uncertain sends, readiness/error handling,
first-page flags, and raster generation for QL-800 and QL-1110NWB. Compression
checks compare decoded raster rows with uncompressed output where supported.
These tests do not establish physical print quality. Real hardware results are
recorded below; other models still require their own validation. Before future
updates, repeat synthetic labels, completion/readiness, and stock mismatch checks.
Do not consume postage or reuse a customer shipping label for driver experiments.

## Hardware validation: October 18 evening / October 19 UTC, 2026

The fork was exercised on our QL-800 with 29×90 mm die-cut stock and QL-1110NWB
with 102 mm continuous stock. Exclusive probe ownership was enforced by stopping
one idle worker at a time, waiting for its pod to exit, then restoring it after
each experiment. The temporary probe pod was removed afterward.

- Four initial labels confirmed both models' start/completion/readiness sequences.
- Two further shipping labels held quality constant while comparing compression.
  The raster payload fell from 116,857 to 18,319 bytes, about 84%. Total completion
  time was similar; this establishes a transfer-size benefit, not faster printing.
- After app rollout, two regular labels and one full-length synthetic shipping
  label passed through the durable API queues. Each reached `completed` after
  device acknowledgement. Wrong-stock jobs were rejected on both models, and
  status queries worked alongside normal queue processing.
- Nine labels in total were confirmed by the devices. Visual quality, barcode
  scanning, and ruler measurements have not been independently confirmed.
- Sanitized raw replies from the initial probes are retained as hardware-free
  regression fixtures in `tests/fixtures/`. Full private traces remain outside Git
  under `~/.local/share/brother-ql-tests/` on the operator's Mac.

For a future controlled probe, first ensure no other process owns the USB device:

```sh
# Status only; provide the actual device identifier. Output must be a new file.
.venv/bin/python tools/hardware_probe.py --model QL-800 \
  --identifier usb://0x04f9:0x209b --output /tmp/ql800-check.json
# Adding --print explicitly consumes two synthetic labels and never retries them.
```

The probe validates the model and stock before sending raster data, records a report
even on failures, and requires a new output filename to prevent accidental reuse.
It is an experiment utility, not a substitute for a durable production job queue.

## Brother software investigation

Brother publishes a [QL-800 raster reference](https://download.brother.com/welcome/docp100278/cv_ql800_eng_raster_101.pdf)
and a [QL-1110NWB manual index including its raster reference](https://support.brother.com/g/b/manualtop.aspx?c=us&lang=en&prod=lpql1110nwbeus).
Its [QL-800 Linux downloads](https://support.brother.com/g/b/downloadlist.aspx?c=us_ot&lang=en&os=131&prod=lpql800eus)
and [QL-1110NWB Linux downloads](https://support.brother.com/g/b/downloadlist.aspx?c=us&lang=en&os=130&prod=lpql1110nwbeus)
also list CUPS wrapper source code. Wrapper source is not proof that the proprietary
raster engine's source is available.

The download indexes returned HTTP 403 during this investigation. No Brother binary
has been obtained, executed, or decompiled, and no official command trace is claimed.
The next comparison should use official packages and a synthetic pattern containing
text, a barcode, borders, and alignment marks. Capture commands/replies with timings
for each printer, changing one setting at a time (stock, cut, quality, compression,
red/black where supported). Compare command sequences and reconstructed pixels before
investigating specific undocumented behavior in native libraries. Keep downloaded
vendor installers, binaries, and captures outside Git; record versions and checksums.
USB ownership must remain exclusive: stop the relevant application worker deliberately
before connecting a vendor driver to that physical printer, then restore it after the
experiment. Do not attach a competing driver to the live queue.

## Upstream model and label reference

The following compatibility list is inherited from upstream. It is not a claim that
this fork has physically revalidated every device.

## Verified models
### Verified devices

✓ means the device was verified by the original project

QL-500 (✓), QL-550 (✓), QL-560 (✓), QL-570 (✓), QL-580N
QL-600 (✓), QL-650TD
QL-700 (✓), QL-710W (✓), QL-720NW (✓)
QL-800 (✓), QL-810W (✓), QL-820NWB (✓)
QL-1050 (✓), QL-1060N (✓),
QL-1100 (✓), QL-1110NWB, QL-1115NWB.

### Verified labels

The available label names can be listed with `brother_ql info labels`:

     Name      Printable px   Description
     12         106           12mm endless
     12+17      306           12mm endless
     18         234           18mm endless
     29         306           29mm endless
     38         413           38mm endless
     50         554           50mm endless
     54         590           54mm endless
     62         696           62mm endless
     62red      696           62mm endless (black/red/white)
     102       1164           102mm endless
     103       1200           104mm endless
     104       1200           104mm endless
     17x54      165 x  566    17mm x 54mm die-cut
     17x87      165 x  956    17mm x 87mm die-cut
     23x23      202 x  202    23mm x 23mm die-cut
     29x42      306 x  425    29mm x 42mm die-cut
     29x90      306 x  991    29mm x 90mm die-cut
     39x90      413 x  991    38mm x 90mm die-cut
     39x48      425 x  495    39mm x 48mm die-cut
     52x29      578 x  271    52mm x 29mm die-cut
     54x29      598 x  271    54mm x 29mm die-cut
     60x86      672 x  954    60mm x 87mm die-cut
     62x29      696 x  271    62mm x 29mm die-cut
     62x100     696 x 1109    62mm x 100mm die-cut
     102x51    1164 x  526    102mm x 51mm die-cut
     102x152   1164 x 1660    102mm x 153mm die-cut
     103x164   1200 x 1822    104mm x 164mm die-cut
     d12         94 x   94    12mm round die-cut
     d24        236 x  236    24mm round die-cut
     d58        618 x  618    58mm round die-cut
     pt12       - unknown -   12mm endless
     pt18       - unknown -   18mm endless
     pt24       - unknown -   24mm endless
     pt36       - unknown -   36mm endless

### Backends

There are multiple backends for connecting to the printer available (✔: supported, ✘: not supported):

Backend | Kind | Linux | Mac OS | Windows
-------|-------|---------|---------|--------
network (1) | TCP | ✔ | ✔ | ✔
linux\_kernel | USB | ✔ (2) | ✘ | ✘
pyusb (3) | USB | ✔ (3.1) | ✔ (3.2) | ✔ (3.3)

Warning: when using one of the USB backends make sure the Editor Lite feature is turned off (if your model supports it), otherwise the USB Printer interface won't be detected.

## Significant Changes:
v 1.3:
- Added detection of more media and commands to list and configure settings https://github.com/matmair/brother_ql-inventree/pull/57
- Added new cli command for getting the status of printers https://github.com/matmair/brother_ql-inventree/pull/53

v1.2:
- Remove support for Python 2 https://github.com/matmair/brother_ql-inventree/pull/43 / https://github.com/matmair/brother_ql-inventree/pull/45
- Added support for PT-E550W https://github.com/matmair/brother_ql-inventree/pull/44
- Added label support for 12+17 https://github.com/matmair/brother_ql-inventree/pull/42

v1.1:
- Support for Pillow 10.x https://github.com/matmair/brother_ql-inventree/pull/37
v1.0:

- Renamed the package to `brother_ql-inventree` and added a release action https://github.com/matmair/brother_ql-inventree/pull/16
- Added printer support for QL-600 https://github.com/matmair/brother_ql-inventree/pull/17 , PT-P950NW https://github.com/matmair/brother_ql-inventree/pull/6 , QL-1100, L-1100NWB, QL-1115NWB https://github.com/matmair/brother_ql-inventree/pull/18
- Added label support for DK-1234 https://github.com/matmair/brother_ql-inventree/pull/22 , 54x29  https://github.com/matmair/brother_ql-inventree/pull/19 , DK22246 https://github.com/matmair/brother_ql-inventree/pull/20, ...

Read the full old Readme [here](https://github.com/matmair/brother_ql-inventree/blob/cleanup/OLD_README.md).
