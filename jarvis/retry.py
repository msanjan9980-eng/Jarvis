"""Tiny retry wrapper for googleapiclient execute() calls."""
import time
from googleapiclient.errors import HttpError


def execute_with_retry(request, attempts=3, base_delay=0.5):
    last = None
    for i in range(attempts):
        try:
            return request.execute()
        except HttpError as e:
            code = getattr(e.resp, "status", None)
            if code in (429, 500, 502, 503, 504):
                last = e
                time.sleep(base_delay * (2 ** i))
                continue
            raise
    raise last
