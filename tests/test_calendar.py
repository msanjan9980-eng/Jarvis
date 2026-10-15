"""Unit tests for jarvis.calendar conflict detection."""
import unittest
from datetime import datetime
from jarvis.calendar import find_conflicts


def _ev(summary, start, end):
    return {"summary": summary, "start": start, "end": end,
            "id": summary, "calendar_id": "primary", "calendar": "primary", "attendees": []}


class TestConflicts(unittest.TestCase):
    def test_no_conflict_when_sequential(self):
        a = _ev("a", datetime(2026,1,1,10), datetime(2026,1,1,11))
        b = _ev("b", datetime(2026,1,1,11), datetime(2026,1,1,12))
        self.assertEqual(find_conflicts([a, b]), [])

    def test_overlap_partial(self):
        a = _ev("a", datetime(2026,1,1,10), datetime(2026,1,1,11))
        b = _ev("b", datetime(2026,1,1,10,30), datetime(2026,1,1,11,30))
        self.assertEqual(len(find_conflicts([a, b])), 1)

    def test_overlap_containment(self):
        a = _ev("a", datetime(2026,1,1,10), datetime(2026,1,1,12))
        b = _ev("b", datetime(2026,1,1,10,30), datetime(2026,1,1,11))
        self.assertEqual(len(find_conflicts([a, b])), 1)

    def test_three_way_conflict(self):
        a = _ev("a", datetime(2026,1,1,10), datetime(2026,1,1,11))
        b = _ev("b", datetime(2026,1,1,10,30), datetime(2026,1,1,11,30))
        c = _ev("c", datetime(2026,1,1,10,45), datetime(2026,1,1,11,15))
        self.assertEqual(len(find_conflicts([a, b, c])), 3)

    def test_touching_not_conflict(self):
        a = _ev("a", datetime(2026,1,1,10), datetime(2026,1,1,11))
        b = _ev("b", datetime(2026,1,1,11), datetime(2026,1,1,11,30))
        self.assertEqual(find_conflicts([a, b]), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
