#  IrisFacadeRenderer: ENVELOPE.md v1 values in ioc_enrichment -> one HTML tab per service.
#
#  Standard library only, so the tests reach it without starting IRIS: importing IRIS's
#  `app`, or `iris_interface`, which imports `app`, runs IRIS's post-init. The IRIS side
#  (hook registration, the tab writer) lives in IrisFacadeRendererInterface.
#
#  The output carries no `style`: IRIS 2.4.29 strips it. State is a Bootstrap 4.6 badge,
#  recoloured by IRIS's atlantis.css, and every tag and attribute is in the allow list of
#  IRIS's filter for `html` attribute fields, which therefore leaves the output unchanged.

import html

import iris_facade_renderer_module.IrisFacadeRendererConfig as conf

SERVICE_TABS = {"vt": "VT Report", "abuseipdb": "AbuseIPDB Report", "urlscan": "URLScan Report"}
SERVICE_TITLES = {"vt": "VirusTotal", "abuseipdb": "AbuseIPDB", "urlscan": "URLScan"}

# Detail rows per service: label, key in the record, expected type. A key that is missing,
# null or of another type is left out.
DETAILS = {
    "vt": [("Country", "country", str), ("AS owner", "as_owner", str),
           ("Network", "network", str), ("Reputation", "reputation", int),
           ("Type", "type_description", str), ("Meaningful name", "meaningful_name", str)],
    "abuseipdb": [("ISP", "isp", str), ("Country", "countryCode", str),
                  ("Usage type", "usageType", str), ("Domain", "domain", str),
                  ("Total reports", "totalReports", int), ("Last reported", "lastReportedAt", str)],
}

UNRECOGNISED = "This value is not an ENVELOPE.md v1 response or error."

# The shapes of ENVELOPE.md v1 the renderer reads (SPEC §5.4).
KNOWN, UNKNOWN, NO_FINDINGS, ERROR = "known", "unknown", "no findings", "error"
_ENVELOPE_KEYS = {"query", "known", "verdict", "report"}
_ERROR_KEYS = {"code", "message", "upstream"}


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _has_score(verdict):
    return isinstance(verdict, dict) and _is_number(verdict.get("score"))


def classify(value):
    """The v1 shape of a value: KNOWN, UNKNOWN, NO_FINDINGS, ERROR, or None if it has none."""
    if not isinstance(value, dict):
        return None
    if set(value) == {"error"}:
        err = value["error"]
        if (isinstance(err, dict) and set(err) <= _ERROR_KEYS
                and isinstance(err.get("code"), str) and isinstance(err.get("message"), str)):
            return ERROR
        return None
    if set(value) != _ENVELOPE_KEYS:
        return None
    query = value["query"]
    if not isinstance(query, dict) or not isinstance(query.get("artifact"), str):
        return None
    known, verdict = value["known"], value["verdict"]
    if known is True:
        return KNOWN if _has_score(verdict) else None
    if known is False:
        if verdict is None and value["report"] is None:
            return UNKNOWN
        return NO_FINDINGS if _has_score(verdict) else None
    return None


def tab_name(key):
    """The tab for a service key. Written unescaped: IRIS's templates autoescape tab names."""
    return SERVICE_TABS.get(key, "%s Report" % key)


def _esc(value):
    return html.escape(str(value), quote=True)


def _badge(cls, text):
    return '<span class="badge %s">%s</span>' % (cls, _esc(text))


def _heading(key, badge):
    return "<h3>%s %s</h3>" % (_esc(SERVICE_TITLES.get(key, key)), badge)


def _footer(key):
    return ('<p class="small text-muted">via %s facade &middot; rendered by IrisFacadeRenderer %s</p>'
            % (_esc(key), conf.module_version))


def _table(rows):
    return ('<table class="table table-sm"><tbody>%s</tbody></table>'
            % "".join("<tr><th>%s</th><td>%s</td></tr>" % (_esc(k), _esc(v)) for k, v in rows))


def _record(env):
    """The upstream's object: report.attributes (VirusTotal) or report itself (AbuseIPDB)."""
    report = env.get("report")
    if not isinstance(report, dict):
        return {}
    attributes = report.get("attributes")
    return attributes if isinstance(attributes, dict) else report


def _detail_rows(key, record):
    rows = []
    for label, field, kind in DETAILS.get(key, []):
        v = record.get(field)
        if (_is_int(v) if kind is int else isinstance(v, kind)):
            rows.append((label, v))
    return rows


def _stats(env, record):
    """The integer analysis stats: verdict.stats when it is an object, else the record's."""
    stats = env["verdict"].get("stats")
    if not isinstance(stats, dict):
        stats = record.get("last_analysis_stats")
    if not isinstance(stats, dict):
        return {}
    return {k: n for k, n in stats.items() if isinstance(k, str) and _is_int(n)}


def _names(record):
    names = record.get("names")
    if not isinstance(names, list):
        return []
    return [n for n in names if isinstance(n, str)][:5]


def _artifact(env):
    return "<p>artifact: <code>%s</code></p>" % _esc(env["query"]["artifact"])


def render_value(key, value):
    """HTML for one service key's value, and whether the value is a v1 shape."""
    shape = classify(value)

    if shape == ERROR:
        err = value["error"]
        body = (_heading(key, _badge("badge-warning", "lookup failed (%s)" % err["code"]))
                + "<p>%s</p>" % _esc(err["message"]))
    elif shape == UNKNOWN:
        body = (_heading(key, _badge("badge-light", "unknown (no record)"))
                + "<p>No record upstream for <code>%s</code>.</p>" % _esc(value["query"]["artifact"]))
    elif shape == NO_FINDINGS:
        record = _record(value)
        rows = _detail_rows(key, record)
        body = (_heading(key, _badge("badge-light", "no findings (score %s)" % value["verdict"]["score"]))
                + _artifact(value) + (_table(rows) if rows else ""))
    elif shape == KNOWN:
        record = _record(value)
        score = value["verdict"]["score"]
        stats = _stats(value, record)
        total = sum(stats.values())
        text = "score %s/%s" % (score, total) if total else "score %s" % score
        rows = _detail_rows(key, record)
        names = _names(record)
        body = (_heading(key, _badge("badge-danger" if score > 0 else "badge-success", text))
                + _artifact(value) + (_table(rows) if rows else ""))
        if stats:
            body += "<h4>Analysis stats</h4>" + _table(sorted(stats.items()))
        if names:
            body += "<p><strong>Names:</strong> %s</p>" % _esc(", ".join(names))
    else:
        return render_unrecognised(key), False

    return body + _footer(key), True


def render_unrecognised(key):
    """The ? tab: nothing in it is taken from the value."""
    return _heading(key, _badge("badge-light", "?")) + "<p>%s</p>" % UNRECOGNISED + _footer(key)


def render_iocs(iocs, write_tab, log):
    """Render and write every service key of every IOC. True when every tab was rendered
    and written; a value of no v1 shape is rendered, as "?", and does not count against it.

    write_tab(ioc, tab, html) returns True when IRIS wrote the tab; a false return or an
    exception is a failed tab. A failed tab, and a fault while rendering a value, are
    logged while the other keys and IOCs go on, and make the call report failure.
    """
    all_written = True
    for ioc in iocs:
        ioc_id = getattr(ioc, "ioc_id", "?")
        enrichment = getattr(ioc, "ioc_enrichment", None)
        if not isinstance(enrichment, dict) or not enrichment:
            log.info("IOC #%s: no ioc_enrichment, nothing to render" % ioc_id)
            continue
        for key, value in enrichment.items():
            tab = tab_name(key)
            try:
                body, recognised = render_value(key, value)
            except Exception as e:  # a fault in this module, not in the data: one tab only,
                body, recognised = render_unrecognised(key), True  # but the call fails
                all_written = False
                log.error('IOC #%s: %r: rendering failed (%s: %s), rendered as "?"'
                          % (ioc_id, key, type(e).__name__, e))
            if not recognised:
                log.warning('IOC #%s: %r: not an ENVELOPE.md v1 value, rendered as "?"' % (ioc_id, key))
            try:
                written, reason = bool(write_tab(ioc, tab, body)), "IRIS did not write it"
            except Exception as e:  # any failure of one tab must not stop the others
                written, reason = False, "%s: %s" % (type(e).__name__, e)
            if written:
                log.info("IOC #%s: rendered tab %r" % (ioc_id, tab))
            else:
                all_written = False
                log.error("IOC #%s: tab %r not written: %s" % (ioc_id, tab, reason))
    return all_written
