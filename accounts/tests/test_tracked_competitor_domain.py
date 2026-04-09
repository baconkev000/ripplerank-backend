"""Normalization for TrackedCompetitor.domain."""

from django.test import TestCase

from accounts.domain_utils import normalize_tracked_competitor_domain


class NormalizeTrackedCompetitorDomainTests(TestCase):
    def test_strips_path_query_and_www(self) -> None:
        self.assertEqual(
            normalize_tracked_competitor_domain("https://WWW.Example.com/foo/bar?x=1#h"),
            "example.com",
        )

    def test_bare_host_with_path(self) -> None:
        self.assertEqual(
            normalize_tracked_competitor_domain("competitor.io/pricing"),
            "competitor.io",
        )

    def test_drops_default_ports(self) -> None:
        self.assertEqual(
            normalize_tracked_competitor_domain("https://x.com:443/"),
            "x.com",
        )
        self.assertEqual(
            normalize_tracked_competitor_domain("http://x.com:80"),
            "x.com",
        )

    def test_empty_invalid(self) -> None:
        self.assertIsNone(normalize_tracked_competitor_domain(""))
        self.assertIsNone(normalize_tracked_competitor_domain("   "))
