#!/usr/bin/env python3
"""Explicit, bounded hardware checks. Never run alongside another USB owner."""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from brother_ql.backends import backend_factory
from brother_ql.backends.helpers import get_status
from brother_ql.print_queue import BrotherPrintQueue
from brother_ql.raster import BrotherQLRaster


def test_pattern(model, variant, run_id):
    width, height = (306, 991) if model == 'QL-800' else (1164, 708)
    image = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype('DejaVuSans.ttf', 23 if width == 306 else 38)
    except OSError:
        font = ImageFont.load_default(size=23 if width == 306 else 38)
    draw.rectangle((3, 3, width - 4, height - 4), outline='black', width=2)
    lines = ['SPOREPRINT TEST', 'NOT POSTAGE', model, run_id, variant,
             '0123456789', 'Alignment / contrast']
    y = 24
    for line in lines:
        draw.text((16, y), line, fill='black', font=font)
        y += 42 if width == 306 else 57
    # Alternating bars, alignment crosses, and a true 10 mm scale at 300 dpi.
    for x in range(18, width - 18, 8):
        draw.rectangle((x, y + 10, x + 2, y + 75), fill='black')
    y += 110
    draw.line((18, y, 136, y), fill='black', width=3)
    for x in (18, 136):
        draw.line((x, y - 10, x, y + 10), fill='black', width=2)
    draw.text((18, y + 15), '10 mm', fill='black', font=font)
    return image


class TraceTransport:
    def __init__(self, backend, events):
        self.backend, self.events = backend, events
        self.started = time.monotonic()

    def write(self, data):
        self.events.append({'seconds': round(time.monotonic() - self.started, 4),
                            'direction': 'write', 'bytes': len(data)})
        self.backend.write(data)

    def read(self, length=32):
        data = self.backend.read(length)
        if data:
            self.events.append({'seconds': round(time.monotonic() - self.started, 4),
                                'direction': 'read', 'hex': bytes(data).hex()})
        return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', choices=['QL-800', 'QL-1110NWB'], required=True)
    parser.add_argument('--identifier', required=True)
    parser.add_argument('--print', dest='print_labels', action='store_true',
                        help='Consume exactly two synthetic labels; never retry an uncertain send')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = {'model': args.model, 'run_id': datetime.now(timezone.utc).strftime('%H%M%S'),
              'events': [], 'printed': False}
    # Refuse overwriting an earlier run, and reserve its report before any write.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as report:
        args.output.chmod(0o600)
        backend = None
        try:
            backend = backend_factory('pyusb')['backend_class'](args.identifier)
            transport = TraceTransport(backend, result['events'])
            status = get_status(transport, target_status=0)
            result['before'] = status
            if status['errors'] or status['model'] != args.model or status['phase_code'] != 0:
                raise RuntimeError('Printer model, error, or readiness check failed')
            stock = '29x90' if args.model == 'QL-800' else '102'
            if (status['media_width'], status['media_length'], status['media_code']) != (
                    (29, 90, 0x0b) if args.model == 'QL-800' else (102, 0, 0x0a)):
                raise RuntimeError('Unexpected stock; no raster sent')
            if args.print_labels:
                queue = BrotherPrintQueue(transport, BrotherQLRaster(args.model))
                variants = [('standard', False, True)]
                variants += ([('high-speed', False, False)] if args.model == 'QL-800'
                             else [('compressed', True, True)])
                result['profiles'] = variants
                for variant, compress, hq in variants:
                    queue.queue_image(images=[test_pattern(args.model, variant, result['run_id'])],
                                      label=stock, compress=compress, hq=hq)
                result['printed'] = queue.submit()
                result['uncertain'] = queue.uncertain
                result['last_error'] = queue.last_error
                if not result['printed']:
                    raise RuntimeError('Print not confirmed; inspect labels; do not retry')
            result['after'] = get_status(transport, target_status=0)
        except BaseException as exc:
            result['error'] = f'{type(exc).__name__}: {exc}'
            raise
        finally:
            if backend is not None:
                backend.dispose()
            json.dump(result, report, indent=2)
            report.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'events'}))


if __name__ == '__main__':
    main()
