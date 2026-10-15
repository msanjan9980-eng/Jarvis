"""Unit tests for jarvis.parse.parse_reply."""
import unittest
from datetime import datetime
from jarvis.parse import parse_reply


class TestParseReply(unittest.TestCase):
    REF = datetime(2026, 10, 16, 10, 0)

    def test_plain_yes(self):
        self.assertEqual(parse_reply("Yes")["decision"], "accept")

    def test_yes_case_insensitive(self):
        for s in ["yes", "YES", "Yep", "sure", "Okay", "confirmed", "works for me"]:
            self.assertEqual(parse_reply(s)["decision"], "accept", msg=s)

    def test_plain_no(self):
        self.assertEqual(parse_reply("No")["decision"], "decline")

    def test_no_variants(self):
        for s in ["no thanks", "can't make it", "decline", "busy that day", "doesn't work"]:
            self.assertEqual(parse_reply(s)["decision"], "decline", msg=s)

    def test_explicit_time_is_proposal(self):
        r = parse_reply("How about 14:00?", reference_date=self.REF)
        self.assertEqual(r["decision"], "propose_time")
        self.assertEqual(r["new_start"].hour, 14)
        self.assertEqual(r["new_start"].minute, 0)

    def test_pm_time(self):
        r = parse_reply("Can we do 2pm?", reference_date=self.REF)
        self.assertEqual(r["decision"], "propose_time")
        self.assertEqual(r["new_start"].hour, 14)

    def test_am_time(self):
        r = parse_reply("9am works", reference_date=self.REF)
        # "works" triggers accept; but 9am is earlier than 10:00 ref
        # Given our ordering, "works" wins -> accept. Assert that.
        self.assertEqual(r["decision"], "accept")

    def test_yes_with_time_is_accept(self):
        self.assertEqual(
            parse_reply("Yes, 14:00 works")["decision"], "accept"
        )

    def test_unclear(self):
        self.assertEqual(
            parse_reply("maybe later, we should discuss")["decision"], "unclear"
        )

    def test_empty_is_unclear(self):
        self.assertEqual(parse_reply("")["decision"], "unclear")

    def test_quoted_header_does_not_hijack(self):
        body = (
            "Yes\n\n"
            "On Thu, Oct 15, 2026 at 3:07 PM Sanjan <x@y.com> wrote:\n"
            "> hi\n"
        )
        self.assertEqual(parse_reply(body)["decision"], "accept")

    def test_quoted_lines_ignored(self):
        body = "> No thanks\nYes\n"
        # the leading "> No thanks" line is stripped; remaining is Yes
        self.assertEqual(parse_reply(body)["decision"], "accept")


if __name__ == "__main__":
    unittest.main(verbosity=2)
