import logging
from collections import deque
import time
import math

from brother_ql.reader import StatusReader
from brother_ql.conversion import queue_convert
from brother_ql.raster import BrotherQLRaster
from brother_ql.backends import BrotherQLBackendGeneric


logger = logging.getLogger(__name__)


class BrotherPrintQueue:
    def __init__(self, printer: BrotherQLBackendGeneric, rasterizer: BrotherQLRaster,
                 completion_timeout=30, ready_timeout=3, status_timeout=3):
        for value in (completion_timeout, ready_timeout, status_timeout):
            if not math.isfinite(value) or value <= 0:
                raise ValueError("Printer timeouts must be finite and positive")
        self.completion_timeout = completion_timeout
        self.ready_timeout = ready_timeout
        self.status_timeout = status_timeout
        self._print_queue = deque()
        self._qlr = rasterizer
        self._printer = printer
        self._printing = False
        self.uncertain = False
        self._responses = StatusReader(printer)
        self.status = None
        self.ready = False
        self.last_error = []
        self.page_count = 0
        self.initialize()

    def clear(self):
        """Discard pending pages and acknowledge any uncertain physical print."""
        if self._printing:
            raise RuntimeError("Can't clear images while printing")
        self._print_queue.clear()
        self.page_count = 0
        self.uncertain = False

    def initialize(self):
        if self.uncertain:
            raise RuntimeError("Check the physical label, then clear the queue before resetting")
        self._responses.pending.clear()
        self._qlr.clear()

        # Standard init sequence
        # Invalidate -> Initialize -> Status Request
        self._qlr.add_invalidate()
        self._printer.write(self._qlr.data)
        self._qlr.clear()

        self._qlr.add_initialize()
        self._printer.write(self._qlr.data)
        self._qlr.clear()

        ready = self._validate_status(phase=0, request=True, timeout=self.status_timeout)
        self._printing = False
        self.ready = ready

        self.page_count = len(self._print_queue)

    def queue_image(self, **kwargs):
        if self._printing:
            raise RuntimeError("Can't queue images while printing")
        # BrotherQLRaster page number starts from 0
        self._qlr.page_number = len(self._print_queue)
        page_data = queue_convert(qlr=self._qlr, **kwargs)
        for p in page_data:
            self._print_queue.append(p)
            logger.debug(
                # f"Queued page block {' '.join( map(lambda byte: f'{byte:02X}', p))}"
                f"Queued page block of {len(p)} bytes"
            )
        self.page_count = len(self._print_queue)

    def submit(self, clear_on_failure: bool = False):
        """Submit once; an unconfirmed send requires physical inspection and clear()."""
        if self.uncertain:
            raise RuntimeError("Previous print is uncertain; check the label and clear the queue")
        if self._printing:
            raise RuntimeError("Already printing")
        if not self.ready:
            self.initialize()
        if not self.ready:
            return False
        self._printing = True
        try:
            while self._print_queue:
                if not self._submit_page():
                    if clear_on_failure:
                        self._print_queue.clear()
                    return False
            return True
        finally:
            self.page_count = len(self._print_queue)
            self._printing = False

    def _submit_page(self):
        # Remove before writing: even a raising write may have transferred bytes.
        page_data = self._print_queue.popleft()
        self.uncertain = True
        self.ready = False
        try:
            self._printer.write(page_data)
            # A fast printer may omit a separately observed "started" phase.
            # Completion followed by readiness is sufficient; readiness alone isn't.
            if not self._validate_status(status=1, timeout=self.completion_timeout):
                return False
            if not self._validate_status(status=6, phase=0, timeout=self.ready_timeout):
                return False
            self.uncertain = False
            self.ready = True
            return True
        finally:
            self.page_count = len(self._print_queue)

    def _validate_status(
        self,
        status: int = -1,
        phase: int = -1,
        timeout: int = 10,
        request: bool = False,
    ):
        if request:
            if status != -1:
                raise AttributeError(
                    "Specifying an expected status type is not allowed for requests"
                )
            status = 0  # always 0x00 for requests
            logger.debug("Requesting status")
            self._qlr.clear()
            self._qlr.add_status_information()
            self._printer.write(self._qlr.data)
            self._qlr.clear()

        logger.debug("Waiting for response")
        if status != -1 or phase != -1:
            logger.debug(
                f"Expecting status type 0x{status:02X}, phase type 0x{phase:02X}, timeout {timeout}s"
            )

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                response = self._responses.read(deadline)
            except TimeoutError:
                break
            self.status = response
            if response["errors"]:
                self.last_error = response["errors"]
                return False
            status_match = status == -1 or status == response["status_code"]
            phase_match = phase == -1 or phase == response["phase_code"]
            if status_match and phase_match:
                self.last_error = []
                return True
            # Notifications and other phase changes can precede the expected reply.
        logger.warning("Expected printer status not received within %s seconds", timeout)
        return False
