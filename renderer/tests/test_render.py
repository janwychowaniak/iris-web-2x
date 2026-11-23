"""IrisFacadeRenderer 0.2.0 tests (SPEC §11). Run in the stock base image, where bleach is
IRIS's own 6.1.0: scripts/test-renderer.sh."""
import copy
import types
import unittest
import unittest.mock

import bleach

import iris_2429_filter as iris_filter
import iris_facade_renderer_module as package
import iris_facade_renderer_module.IrisFacadeRendererConfig as conf
from iris_facade_renderer_module import render

STATS = {"harmless": 30, "malicious": 3, "suspicious": 1, "timeout": 0, "undetected": 60}  # T = 94

VT_KNOWN = {
    "query": {"artifact": "198.51.100.7", "type": "ip", "positives_thresh": 1, "msg": "case-1"},
    "known": True,
    "verdict": {"score": 3, "thresh_gte": True, "stats": dict(STATS)},
    "report": {"id": "198.51.100.7", "type": "ip_address", "attributes": {
        "country": "NL", "as_owner": "Example AS", "network": "198.51.100.0/24",
        "reputation": -5, "last_analysis_stats": dict(STATS),
        "names": ["a.exe", "b.exe", "c.exe", "d.exe", "e.exe", "f.exe"]}},
}
VT_UNKNOWN = {
    "query": {"artifact": "203.0.113.9", "type": "ip", "positives_thresh": 1, "msg": None},
    "known": False, "verdict": None, "report": None,
}
ABUSE_RECORD = {"ipAddress": "203.0.113.5", "isp": "Example ISP", "countryCode": "DE",
                "usageType": "Data Center/Web Hosting/Transit", "domain": "example.net",
                "totalReports": 0, "lastReportedAt": None, "abuseConfidenceScore": 0}
ABUSE_NO_FINDINGS = {
    "query": {"artifact": "203.0.113.5", "type": "ip", "threshold": 50, "max_age_days": 90,
              "verbose": False, "msg": None},
    "known": False, "verdict": {"score": 0, "thresh_gte": False}, "report": ABUSE_RECORD,
}
ABUSE_KNOWN = {
    "query": {"artifact": "203.0.113.6", "type": "ip", "threshold": 50, "max_age_days": 90,
              "verbose": False, "msg": None},
    "known": True, "verdict": {"score": 75, "thresh_gte": True},
    "report": dict(ABUSE_RECORD, ipAddress="203.0.113.6", totalReports=12,
                   lastReportedAt="2026-11-20T10:00:00+00:00", abuseConfidenceScore=75),
}
ERROR = {"error": {"code": "UPSTREAM_QUOTA", "message": "VirusTotal quota exceeded",
                   "upstream": {"status": 429, "message": "Quota exceeded"}}}

HOSTILE = "<img src=x onerror=alert(1)>\"'&"
HOSTILE_ESCAPED = "&lt;img src=x onerror=alert(1)&gt;&quot;&#x27;&amp;"


def with_(value, **changes):
    """A deep copy of value with dotted paths replaced; a value of DROP removes the key."""
    v = copy.deepcopy(value)
    for path, new in changes.items():
        *parents, last = path.split("__")
        target = v
        for p in parents:
            target = target[p]
        if new is DROP:
            del target[last]
        else:
            target[last] = new
    return v


DROP = object()


def badge(cls, text):
    return '<span class="badge %s">%s</span>' % (cls, text)


class Log:
    def __init__(self):
        self.lines = []

    def __getattr__(self, level):
        return lambda msg: self.lines.append((level, msg))

    def at(self, level):
        return [m for lv, m in self.lines if lv == level]


class Writer:
    """A tab writer that records its calls; fail maps (ioc_id, tab) to False or an exception."""
    def __init__(self, fail=None):
        self.calls, self.fail = [], fail or {}

    def __call__(self, ioc, tab, body):
        self.calls.append((ioc.ioc_id, tab, body))
        outcome = self.fail.get((ioc.ioc_id, tab), True)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def ioc(ioc_id, enrichment):
    return types.SimpleNamespace(ioc_id=ioc_id, ioc_enrichment=enrichment)


def footer(key):
    return ('<p class="small text-muted">via %s facade &middot; rendered by IrisFacadeRenderer 0.2.0</p>'
            % key)


class TableRows(unittest.TestCase):
    """Every row of SPEC §5.5 to its badge class, text and details."""

    def test_known_positive_with_stats(self):
        out, ok = render.render_value("vt", VT_KNOWN)
        self.assertTrue(ok)
        self.assertIn("<h3>VirusTotal %s</h3>" % badge("badge-danger", "score 3/94"), out)
        self.assertIn("<p>artifact: <code>198.51.100.7</code></p>", out)
        for label, value in [("Country", "NL"), ("AS owner", "Example AS"),
                             ("Network", "198.51.100.0/24"), ("Reputation", "-5")]:
            self.assertIn("<tr><th>%s</th><td>%s</td></tr>" % (label, value), out)
        self.assertIn("<h4>Analysis stats</h4>", out)
        stats_rows = "".join("<tr><th>%s</th><td>%s</td></tr>" % kv for kv in sorted(STATS.items()))
        self.assertIn(stats_rows, out)
        self.assertIn("<p><strong>Names:</strong> a.exe, b.exe, c.exe, d.exe, e.exe</p>", out)
        self.assertNotIn("f.exe", out)
        self.assertTrue(out.endswith(footer("vt")))

    def test_known_positive_without_stats(self):
        out, ok = render.render_value("abuseipdb", ABUSE_KNOWN)
        self.assertTrue(ok)
        self.assertIn(badge("badge-danger", "score 75"), out)
        self.assertIn("<tr><th>Total reports</th><td>12</td></tr>", out)
        self.assertIn("<tr><th>Last reported</th><td>2026-11-20T10:00:00+00:00</td></tr>", out)
        self.assertNotIn("Analysis stats", out)

    def test_known_stats_from_the_record_when_verdict_has_none(self):
        out, _ = render.render_value("vt", with_(VT_KNOWN, verdict__stats=DROP))
        self.assertIn(badge("badge-danger", "score 3/94"), out)

    def test_known_stats_summing_to_zero(self):
        zero = {"malicious": 0, "harmless": 0}
        out, _ = render.render_value("vt", with_(VT_KNOWN, verdict__stats=zero,
                                                 report__attributes__last_analysis_stats=zero))
        self.assertIn(badge("badge-danger", "score 3"), out)

    def test_known_zero(self):
        out, ok = render.render_value("vt", with_(VT_KNOWN, verdict__score=0))
        self.assertTrue(ok)
        self.assertIn(badge("badge-success", "score 0/94"), out)
        self.assertIn("<p>artifact: <code>198.51.100.7</code></p>", out)
        self.assertIn("<h4>Analysis stats</h4>", out)

    def test_known_negative_renders_as_zero_does(self):
        out, _ = render.render_value("vt", with_(VT_KNOWN, verdict__score=-1))
        self.assertIn(badge("badge-success", "score -1/94"), out)

    def test_known_float_score(self):
        out, _ = render.render_value("abuseipdb", with_(ABUSE_KNOWN, verdict__score=4.5))
        self.assertIn(badge("badge-danger", "score 4.5"), out)

    def test_unknown_no_record(self):
        out, ok = render.render_value("vt", VT_UNKNOWN)
        self.assertTrue(ok)
        self.assertEqual(
            out, "<h3>VirusTotal %s</h3>" % badge("badge-light", "unknown (no record)")
            + "<p>No record upstream for <code>203.0.113.9</code>.</p>" + footer("vt"))

    def test_no_findings_with_a_record(self):
        out, ok = render.render_value("abuseipdb", ABUSE_NO_FINDINGS)
        self.assertTrue(ok)
        self.assertIn("<h3>AbuseIPDB %s</h3>" % badge("badge-light", "no findings (score 0)"), out)
        self.assertIn("<p>artifact: <code>203.0.113.5</code></p>", out)
        for label, value in [("ISP", "Example ISP"), ("Country", "DE"),
                             ("Usage type", "Data Center/Web Hosting/Transit"),
                             ("Domain", "example.net"), ("Total reports", "0")]:
            self.assertIn("<tr><th>%s</th><td>%s</td></tr>" % (label, value), out)
        self.assertNotIn("Last reported", out)  # null in the record
        self.assertNotIn("Analysis stats", out)

    def test_error_body(self):
        out, ok = render.render_value("vt", ERROR)
        self.assertTrue(ok)
        self.assertEqual(
            out, "<h3>VirusTotal %s</h3>" % badge("badge-warning", "lookup failed (UPSTREAM_QUOTA)")
            + "<p>VirusTotal quota exceeded</p>" + footer("vt"))

    def test_unrecognised(self):
        out, ok = render.render_value("vt", {"note": "MARKER-FROM-THE-VALUE"})
        self.assertFalse(ok)
        self.assertEqual(
            out, "<h3>VirusTotal %s</h3>" % badge("badge-light", "?")
            + "<p>This value is not an ENVELOPE.md v1 response or error.</p>" + footer("vt"))

    def test_titles(self):
        for key, title in [("vt", "VirusTotal"), ("abuseipdb", "AbuseIPDB"),
                           ("urlscan", "URLScan"), ("shodan", "shodan")]:
            out, _ = render.render_value(key, ERROR)
            self.assertTrue(out.startswith("<h3>%s <span" % title), key)
            self.assertTrue(out.endswith(footer(key)), key)

    def test_urlscan_and_other_keys_have_no_detail_rows(self):
        for key in ("urlscan", "shodan"):
            out, _ = render.render_value(key, VT_KNOWN)
            self.assertNotIn("<th>Country</th>", out)
            self.assertIn("<h4>Analysis stats</h4>", out)


UNRECOGNISED = {
    "known true, score a string": with_(VT_KNOWN, verdict__score="5"),
    "known true, score a boolean": with_(VT_KNOWN, verdict__score=True),
    "known true, score null": with_(VT_KNOWN, verdict__score=None),
    "known true, verdict null": with_(VT_KNOWN, verdict=None),
    "known false, verdict null, a report": with_(VT_UNKNOWN, report={"id": "x"}),
    "known false, report null, a verdict without score": with_(VT_UNKNOWN, verdict={"thresh_gte": False}),
    "known not a boolean": with_(VT_KNOWN, known=1),
    "query a string": with_(VT_KNOWN, query="198.51.100.7"),
    "artifact not a string": with_(VT_KNOWN, query__artifact=5),
    "envelope with an extra key": with_(VT_KNOWN, extra=1),
    "envelope missing a key": with_(VT_KNOWN, report=DROP),
    "error with an extra key": with_(ERROR, error__hint="x"),
    "error code not a string": with_(ERROR, error__code=429),
    "error without a message": with_(ERROR, error__message=DROP),
    "error beside other keys": dict(ERROR, query={"artifact": "x"}),
    "a string": "malicious",
    "a list": [VT_KNOWN],
    "a number": 3,
    "a boolean": True,
    "null": None,
    "an object with other keys": {"score": 3, "known": True},
}


class Unrecognised(unittest.TestCase):
    """Values that are not v1 shapes: the ? tab, one log line, no exception."""

    def test_each_renders_the_question_mark(self):
        for name, value in UNRECOGNISED.items():
            with self.subTest(name):
                out, ok = render.render_value("vt", value)
                self.assertFalse(ok)
                self.assertIn(badge("badge-light", "?"), out)

    def test_each_is_logged_once_and_written(self):
        enrichment = {"k%02d" % i: v for i, v in enumerate(UNRECOGNISED.values())}
        log, writer = Log(), Writer()
        self.assertTrue(render.render_iocs([ioc(7, enrichment)], writer, log))
        self.assertEqual(len(writer.calls), len(enrichment))
        warnings = log.at("warning")
        self.assertEqual(len(warnings), len(enrichment))
        self.assertEqual(warnings[0], "IOC #7: 'k00': not an ENVELOPE.md v1 value, rendered as \"?\"")


class TheLoop(unittest.TestCase):
    """One value or one write affects its own tab only (SPEC §5.6)."""

    def test_a_bad_value_does_not_stop_the_others(self):
        log, writer = Log(), Writer()
        iocs = [ioc(1, {"vt": "garbage", "abuseipdb": ABUSE_KNOWN}), ioc(2, {"vt": VT_KNOWN})]
        self.assertTrue(render.render_iocs(iocs, writer, log))
        self.assertEqual([(i, t) for i, t, _ in writer.calls],
                         [(1, "VT Report"), (1, "AbuseIPDB Report"), (2, "VT Report")])
        self.assertIn(badge("badge-light", "?"), writer.calls[0][2])
        self.assertIn(badge("badge-danger", "score 75"), writer.calls[1][2])
        self.assertIn(badge("badge-danger", "score 3/94"), writer.calls[2][2])
        self.assertEqual(log.at("info"), ["IOC #1: rendered tab 'VT Report'",
                                          "IOC #1: rendered tab 'AbuseIPDB Report'",
                                          "IOC #2: rendered tab 'VT Report'"])

    def test_failed_writes_are_logged_and_the_rest_written(self):
        log = Log()
        writer = Writer(fail={(1, "VT Report"): False,
                              (1, "AbuseIPDB Report"): RuntimeError("commit failed")})
        iocs = [ioc(1, {"vt": VT_KNOWN, "abuseipdb": ABUSE_KNOWN, "urlscan": ERROR}),
                ioc(2, {"vt": VT_UNKNOWN})]
        self.assertFalse(render.render_iocs(iocs, writer, log))
        self.assertEqual(len(writer.calls), 4)
        self.assertEqual(log.at("error"), [
            "IOC #1: tab 'VT Report' not written: IRIS did not write it",
            "IOC #1: tab 'AbuseIPDB Report' not written: RuntimeError: commit failed"])
        self.assertEqual(log.at("info"), ["IOC #1: rendered tab 'URLScan Report'",
                                          "IOC #2: rendered tab 'VT Report'"])

    def test_a_rendering_fault_stays_in_its_tab(self):
        real = render.render_value

        def faulty(key, value):
            if key == "vt":
                raise TypeError("a fault")
            return real(key, value)

        log, writer = Log(), Writer()
        with unittest.mock.patch.object(render, "render_value", faulty):
            ok = render.render_iocs([ioc(1, {"vt": VT_KNOWN, "abuseipdb": ABUSE_KNOWN}),
                                     ioc(2, {"abuseipdb": ABUSE_KNOWN})], writer, log)
        self.assertFalse(ok)  # a bug in the module shows as a failed task
        self.assertEqual([(i, t) for i, t, _ in writer.calls],
                         [(1, "VT Report"), (1, "AbuseIPDB Report"), (2, "AbuseIPDB Report")])
        self.assertEqual(writer.calls[0][2], render.render_unrecognised("vt"))
        self.assertEqual(log.at("error"),
                         ["IOC #1: 'vt': rendering failed (TypeError: a fault), rendered as \"?\""])
        self.assertEqual(log.at("warning"), [])

    def test_no_enrichment_writes_nothing(self):
        for enrichment in (None, {}, [], "text", 5):
            with self.subTest(repr(enrichment)):
                log, writer = Log(), Writer()
                self.assertTrue(render.render_iocs([ioc(3, enrichment)], writer, log))
                self.assertEqual(writer.calls, [])
                self.assertEqual(log.at("info"), ["IOC #3: no ioc_enrichment, nothing to render"])
        log, writer = Log(), Writer()
        self.assertTrue(render.render_iocs([types.SimpleNamespace(ioc_id=4)], writer, log))
        self.assertEqual(writer.calls, [])

    def test_tab_names(self):
        self.assertEqual([render.tab_name(k) for k in ("vt", "abuseipdb", "urlscan", "shodan")],
                         ["VT Report", "AbuseIPDB Report", "URLScan Report", "shodan Report"])
        writer = Writer()
        render.render_iocs([ioc(5, {HOSTILE: ERROR})], writer, Log())
        self.assertEqual(writer.calls[0][1], HOSTILE + " Report")  # IRIS's templates escape it


class WrongTypes(unittest.TestCase):
    """Details without the expected type are left out, never raised."""

    def test_report_a_list(self):
        out, ok = render.render_value("vt", with_(VT_KNOWN, report=[1, 2]))
        self.assertTrue(ok)
        self.assertIn(badge("badge-danger", "score 3/94"), out)  # verdict.stats still count
        self.assertNotIn("<th>Country</th>", out)

    def test_names_keep_strings_only(self):
        out, _ = render.render_value("vt", with_(VT_KNOWN, report__attributes__names=[1, "a.exe", None, ["x"], "b.exe"]))
        self.assertIn("<p><strong>Names:</strong> a.exe, b.exe</p>", out)
        out, _ = render.render_value("vt", with_(VT_KNOWN, report__attributes__names="a.exe"))
        self.assertNotIn("Names:", out)

    def test_details_of_the_wrong_type(self):
        out, _ = render.render_value("vt", with_(VT_KNOWN, report__attributes__country=31,
                                                 report__attributes__reputation=True,
                                                 report__attributes__network=["x"]))
        for label in ("Country", "Reputation", "Network"):
            self.assertNotIn("<th>%s</th>" % label, out)
        self.assertIn("<tr><th>AS owner</th><td>Example AS</td></tr>", out)
        out, _ = render.render_value("abuseipdb", with_(ABUSE_KNOWN, report__totalReports="12"))
        self.assertNotIn("Total reports", out)

    def test_non_integer_stats_left_out(self):
        out, _ = render.render_value("vt", with_(VT_KNOWN, verdict__stats={
            "malicious": 3, "harmless": "30", "suspicious": True, "timeout": 2.5, "undetected": None}))
        self.assertIn(badge("badge-danger", "score 3/3"), out)
        self.assertIn("<tr><th>malicious</th><td>3</td></tr>", out)
        for key in ("harmless", "suspicious", "timeout", "undetected"):
            self.assertNotIn("<th>%s</th>" % key, out)

    def test_stats_sorted_by_key_whatever_their_order(self):
        unsorted = {"undetected": 60, "malicious": 3, "timeout": 0, "harmless": 30, "suspicious": 1}
        self.assertNotEqual(list(unsorted), sorted(unsorted))
        out, _ = render.render_value("vt", with_(VT_KNOWN, verdict__stats=unsorted))
        rows = "".join("<tr><th>%s</th><td>%s</td></tr>" % kv for kv in sorted(unsorted.items()))
        self.assertIn("<h4>Analysis stats</h4><table class=\"table table-sm\"><tbody>%s</tbody></table>" % rows, out)

    def test_stats_not_an_object(self):
        out, _ = render.render_value("vt", with_(VT_KNOWN, verdict__stats=[3],
                                                 report__attributes__last_analysis_stats="many"))
        self.assertIn(badge("badge-danger", "score 3"), out)
        self.assertNotIn("Analysis stats", out)


class Escaping(unittest.TestCase):
    """Every value taken from the data is HTML-escaped."""

    def assertEscaped(self, out):
        self.assertIn(HOSTILE_ESCAPED, out)
        self.assertNotIn("<img", out)

    def test_every_field(self):
        cases = {
            "artifact": ("vt", with_(VT_KNOWN, query__artifact=HOSTILE)),
            "artifact, no record": ("vt", with_(VT_UNKNOWN, query__artifact=HOSTILE)),
            "detail value": ("vt", with_(VT_KNOWN, report__attributes__as_owner=HOSTILE)),
            "a name": ("vt", with_(VT_KNOWN, report__attributes__names=[HOSTILE])),
            "a stats key": ("vt", with_(VT_KNOWN, verdict__stats={HOSTILE: 1})),
            "error code": ("vt", with_(ERROR, error__code=HOSTILE)),
            "error message": ("vt", with_(ERROR, error__message=HOSTILE)),
            "the key": (HOSTILE, ERROR),
            "the key, unrecognised": (HOSTILE, "x"),
        }
        for name, (key, value) in cases.items():
            with self.subTest(name):
                out, _ = render.render_value(key, value)
                self.assertEscaped(out)


class IrisFilter(unittest.TestCase):
    """The output of every row passes IRIS 2.4.29's filter unchanged."""

    def test_unchanged_by_the_filter(self):
        rows = {
            "known, score above 0": ("vt", VT_KNOWN),
            "known, score 0": ("vt", with_(VT_KNOWN, verdict__score=0)),
            "known false, no record": ("vt", VT_UNKNOWN),
            "known false, a record": ("abuseipdb", ABUSE_NO_FINDINGS),
            "error body": ("vt", ERROR),
            "unrecognised": ("vt", "garbage"),
        }
        self.assertEqual(bleach.__version__, "6.1.0")
        for name, (key, value) in rows.items():
            with self.subTest(name):
                out, _ = render.render_value(key, value)
                self.assertNotIn("style", out)
                cleaned = bleach.clean(out, tags=iris_filter._ATTR_HTML_ALLOWED_TAGS,
                                       attributes=iris_filter._ATTR_HTML_ALLOWED_ATTRS,
                                       protocols=iris_filter._ATTR_HTML_ALLOWED_PROTOCOLS,
                                       strip=True)
                self.assertEqual(cleaned, out)


class Identity(unittest.TestCase):
    """What a database registering 0.1.1 holds stays the same (SPEC §5.1)."""

    def test_names(self):
        self.assertEqual(getattr(package, "__iris_module_interface"), "IrisFacadeRendererInterface")
        self.assertEqual((conf.module_name, conf.interface_version, conf.module_version),
                         ("IrisFacadeRenderer", "1.2.0", "0.2.0"))
        self.assertEqual([(p["param_name"], p["default"], p["type"]) for p in conf.module_configuration],
                         [("frr_on_update_hook_enabled", True, "bool"),
                          ("frr_manual_hook_enabled", True, "bool")])
        self.assertEqual((conf.update_hook, conf.manual_hook, conf.manual_hook_name),
                         ("on_postload_ioc_update", "on_manual_trigger_ioc", "Render facade reports"))
        self.assertEqual((conf.field_name, conf.field_type), ("HTML report", "html"))


if __name__ == "__main__":
    unittest.main()
