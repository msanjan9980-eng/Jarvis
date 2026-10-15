"""Unit tests for jarvis.store."""
import os
import tempfile
import unittest

import jarvis.store as store


class TestStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        self.tmp.close()
        os.remove(self.tmp.name)
        self._orig = store.PENDING_PATH
        store.PENDING_PATH = self.tmp.name

    def tearDown(self):
        if os.path.exists(self.tmp.name):
            os.remove(self.tmp.name)
        store.PENDING_PATH = self._orig

    def test_add_and_load(self):
        store.add_pending({"proposal_msg_id": "m1", "summary": "x"})
        e = store.load_pending()
        self.assertEqual(len(e), 1)
        self.assertEqual(e[0]["status"], "pending")
        self.assertIn("created_at", e[0])

    def test_pending_only_filters_resolved(self):
        store.add_pending({"proposal_msg_id": "m1", "summary": "x"})
        store.add_pending({"proposal_msg_id": "m2", "summary": "y"})
        store.mark_resolved("m1", "rescheduled")
        self.assertEqual([p["proposal_msg_id"] for p in store.pending_only()], ["m2"])

    def test_mark_resolved_sets_status(self):
        store.add_pending({"proposal_msg_id": "m1", "summary": "x"})
        store.mark_resolved("m1", "declined")
        e = store.load_pending()
        self.assertEqual(e[0]["status"], "declined")
        self.assertIn("resolved_at", e[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
