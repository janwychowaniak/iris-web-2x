#!/usr/bin/env python3
"""The browser test of the Overview's columns and the notes editor (SPEC.md §9.2).

    check-ui.py <image> --old <image> [--browser <path>]
    check-ui.py --control <image> [--browser <path>]

IRIS runs from the image's entrypoint against the stock 2.4.29 database, behind the stock
2.4.29 nginx with a certificate made for the run. A headless Chromium-family browser,
driven by Playwright, uses it through browser profiles kept on disk for the whole run. The
app starts as --old, where the first profile loads the Overview and a note, restarts and
loads them again; the app is then swapped for <image>, restarted with the variables of T13
and then of T15, and swapped back to --old. Each check prints "ok" or "FAIL", tagged [new],
which holds only with the change, or [same], which holds on both images. With --control,
<image> is also --old, and the run passes when every [new] check fails and every [same]
check passes.

The browser is Google Chrome, Playwright's "chrome" channel, unless --browser names another
Chromium-family browser. It accepts the run's certificate by its key
(--ignore-certificate-errors-spki-list), so it caches as for a trusted site: Chrome keeps
nothing on disk that it loads past an ignored certificate error. The tool is installed with
its hashes checked, into a virtual environment, as CI does:

    python3 -m venv <dir>
    <dir>/bin/pip install --require-hashes --no-deps -r scripts/check-ui-requirements.txt
    <dir>/bin/python -I scripts/check-ui.py ...

Every secret is generated here, kept in a file only this run reads, masked in the GitHub
Actions log, and never printed: output that may carry one is redacted first. Containers and
the network are named iw2x-ui-<pid>-* and removed on exit, with their anonymous volumes.
The browser puts its process socket under TMPDIR, so TMPDIR must be short or unset.
"""
import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import shutil
import signal
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

DB_IMAGE = ("ghcr.io/dfir-iris/iriswebapp_db"
            "@sha256:081ad194332887ca584a9240e8e9dea94129a235e8b38ff42c1938358be432f5")
NGINX_IMAGE = ("ghcr.io/dfir-iris/iriswebapp_nginx"
               "@sha256:887b1eb8ceae5b1e1483a4a7601d79a6b070e314db5772a617e0a9190c556644")
ADMIN = "administrator"

# The Overview's columns, (identifier, title), in the table's order (SPEC.md §6.1).
COLUMNS = [("outcome", "Outcome"), ("case_id", "Case ID"), ("severity", "Severity"),
           ("title", "Title"), ("customer", "Customer"), ("classification", "Classification"),
           ("state", "State"), ("tags", "Tags"), ("open_since", "Open since"),
           ("open_date", "Open date"), ("tasks", "Tasks"), ("owner", "Owner")]
TITLES = [title for _, title in COLUMNS]
TOGGLED = [t for t in TITLES if t != "Title"]
STOCK = TITLES[3:]  # the columns 2.4.29 shows

# T13 leaves Title out, as a deployment may, since Title is shown anyway; T15 lists it.
T13_ENV = {"IW2X_OVERVIEW_COLUMNS": "case_id,severity,owner", "IW2X_NOTE_EDITOR": "hidden"}
T13_SHOWN = ["Case ID", "Severity", "Title", "Owner"]
T15_ENV = {"IW2X_OVERVIEW_COLUMNS": "title,bogus", "IW2X_NOTE_EDITOR": "maybe"}
LINE_STOCK = ("iris-web-2x defaults: Overview columns title,customer,classification,state,tags,"
              "open_since,open_date,tasks,owner (2.4.29); note editor shown (2.4.29)")
LINE_T13 = ("iris-web-2x defaults: Overview columns case_id,severity,title,owner "
            "(IW2X_OVERVIEW_COLUMNS); note editor hidden (IW2X_NOTE_EDITOR)")
WARN_COLUMNS = ("iris-web-2x: IW2X_OVERVIEW_COLUMNS='title,bogus' cannot be used "
                "(unknown column 'bogus'); the default of 2.4.29 applies")
WARN_EDITOR = ("iris-web-2x: IW2X_NOTE_EDITOR='maybe' cannot be used "
               "(expected 'shown' or 'hidden'); the default of 2.4.29 applies")

CASES, FALSE_POSITIVE, CLOSED = 30, 5, 3  # created cases: open false positives, closed ones
OVERVIEW, NOTES = "/overview?cid=1", "/case/notes?cid=1"
SCRIPTS = ("/static/assets/js/iris/overview.js", "/static/assets/js/iris/case.notes.js")
CONTROL = '[title="Toggle columns"]'
COLLECTION = ".dt-button-collection"  # it holds the list, but has no size of its own: the list
ITEMS = COLLECTION + " .buttons-columnVisibility"  # is absolutely positioned, so it is seen by its items


class Failed(Exception):
    pass


def expect(ok, detail):
    if not ok:
        raise Failed(detail)


def first_line(e):
    text = str(e).strip().splitlines()
    return text[0] if text else type(e).__name__


class Stack:
    """The database, the app and nginx, on a network of their own."""

    def __init__(self, work):
        self.work = work
        p = "iw2x-ui-%d" % os.getpid()
        self.net, self.db, self.app, self.nginx = p + "-net", p + "-db", p + "-app", p + "-nginx"
        self.secrets = [secrets.token_hex(24) for _ in range(6)]
        if os.environ.get("GITHUB_ACTIONS"):
            for s in self.secrets:
                print("::add-mask::" + s, flush=True)
        (pg, pga, key, salt, self.password, self.api_key) = self.secrets
        self.env = work / "iris.env"
        old = os.umask(0o077)
        try:
            self.env.write_text("\n".join([
                "POSTGRES_USER=postgres", "POSTGRES_PASSWORD=" + pg,
                "POSTGRES_ADMIN_USER=raptor", "POSTGRES_ADMIN_PASSWORD=" + pga,
                "POSTGRES_DB=iris_db", "POSTGRES_SERVER=" + self.db, "POSTGRES_PORT=5432",
                "DB_RETRY_COUNT=60", "DB_RETRY_DELAY=2", "DOCKERIZED=1",
                "IRIS_SECRET_KEY=" + key, "IRIS_SECURITY_PASSWORD_SALT=" + salt,
                "IRIS_ADM_PASSWORD=" + self.password, "IRIS_ADM_API_KEY=" + self.api_key,
                "IRIS_AUTHENTICATION_TYPE=local", "CELERY_BROKER=amqp://%s-rabbitmq" % p,
                "PYTHONDONTWRITEBYTECODE=1", ""]))
        finally:
            os.umask(old)
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        self.base = "https://localhost:%d" % self.port
        self.api_base = "https://127.0.0.1:%d" % self.port
        self.cert, self.spki = self._certificate()
        self.tls = ssl.create_default_context(cafile=str(self.cert))  # the run's own nginx

    def redact(self, text):
        for s in self.secrets:
            text = text.replace(s, "***")
        return text

    def _certificate(self):
        cert, key = self.work / "iw2x.crt", self.work / "iw2x.key"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt",
                        "ec_paramgen_curve:prime256v1", "-nodes", "-days", "2",
                        "-subj", "/CN=localhost",
                        "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1",
                        "-keyout", str(key), "-out", str(cert)], check=True, capture_output=True)
        key.chmod(0o644)  # read by nginx's www-data, inside its container only
        pem = subprocess.run(["openssl", "x509", "-in", str(cert), "-noout", "-pubkey"],
                             check=True, capture_output=True).stdout
        der = subprocess.run(["openssl", "pkey", "-pubin", "-outform", "DER"], input=pem,
                             check=True, capture_output=True).stdout
        return cert, base64.b64encode(hashlib.sha256(der).digest()).decode()

    @staticmethod
    def docker(*args, check=True):
        r = subprocess.run(["docker", *args], capture_output=True, text=True)
        if check and r.returncode:
            raise RuntimeError("docker %s: %s" % (args[0], r.stderr.strip()[-300:]))
        return r.stdout + r.stderr

    def start(self, image, env=None):
        self.docker("network", "create", self.net)
        self.docker("run", "-d", "--name", self.db, "--network", self.net,
                    "--env-file", str(self.env), DB_IMAGE)
        for _ in range(90):
            if not subprocess.run(["docker", "exec", self.db, "pg_isready", "-q", "-h", "127.0.0.1",
                                   "-U", "postgres"], capture_output=True).returncode:
                break
            time.sleep(2)
        else:
            raise RuntimeError("the stock database did not start")
        self._run_app(image, env)
        self.docker("create", "--name", self.nginx, "--network", self.net,
                    "-p", "127.0.0.1:%d:%d" % (self.port, self.port),
                    "-e", "IRIS_UPSTREAM_SERVER=" + self.app, "-e", "IRIS_UPSTREAM_PORT=8000",
                    "-e", "INTERFACE_HTTPS_PORT=%d" % self.port, "-e", "SERVER_NAME=localhost",
                    "-e", "CERT_FILENAME=iw2x.crt", "-e", "KEY_FILENAME=iw2x.key", NGINX_IMAGE)
        for name in ("iw2x.crt", "iw2x.key"):
            self.docker("cp", str(self.work / name), "%s:/www/certs/%s" % (self.nginx, name))
        self.docker("start", self.nginx)
        self._ready()

    def swap(self, image, env=None):
        self.docker("rm", "-f", "-v", self.app)
        self._run_app(image, env)
        self.docker("restart", self.nginx)  # it resolves the app's name once
        self._ready()

    def _run_app(self, image, env):
        extra = []
        for k, v in (env or {}).items():
            extra += ["-e", "%s=%s" % (k, v)]
        self.docker("run", "-d", "--name", self.app, "--network", self.net,
                    "--env-file", str(self.env), *extra, image,
                    "./iris-entrypoint.sh", "iriswebapp")

    def _ready(self):
        deadline = time.time() + 300
        while time.time() < deadline:
            for c in (self.app, self.nginx):
                if self.docker("inspect", "-f", "{{.State.Running}}", c, check=False).strip() != "true":
                    raise RuntimeError("%s stopped; the end of its log:\n%s" % (c, "\n".join(
                        self.redact(self.docker("logs", c, check=False)).splitlines()[-30:])))
            try:
                with urllib.request.urlopen(self.api_base + "/login", context=self.tls, timeout=10) as r:
                    if r.status == 200:
                        return
            except (urllib.error.URLError, OSError):
                pass
            time.sleep(2)
        raise RuntimeError("IRIS did not answer through nginx; the end of the app's log:\n"
                           + "\n".join(self.redact(self.app_log()).splitlines()[-30:]))

    def app_log(self):
        return self.docker("logs", self.app, check=False)

    def access_log(self):
        return self.docker("exec", self.nginx, "cat", "/var/log/nginx/audit_platform_access.log",
                           check=False).splitlines()

    def api(self, method, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.api_base + path, data=data, method=method, headers={
            "Authorization": "Bearer " + self.api_key, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, context=self.tls, timeout=30) as r:
            answer = json.load(r)
        if answer.get("status") != "success":
            raise RuntimeError("%s %s: %s" % (method, path, self.redact(json.dumps(answer))[:300]))
        return answer["data"]

    def cleanup(self):
        for c in (self.nginx, self.app, self.db):
            subprocess.run(["docker", "rm", "-f", "-v", c], capture_output=True)
        subprocess.run(["docker", "network", "rm", self.net], capture_output=True)


class Profile:
    """One browser profile on disk, signed in as the administrator, for the whole run."""

    def __init__(self, run, name):
        self.run, self.name = run, name
        self._launch()
        self.login()

    def _launch(self):
        run = self.run
        kwargs = dict(user_data_dir=str(run.work / ("profile-" + self.name)), headless=True,
                      args=["--ignore-certificate-errors-spki-list=" + run.stack.spki],
                      viewport={"width": 1920, "height": 1080}, base_url=run.stack.base)
        if run.args.browser:
            kwargs["executable_path"] = run.args.browser
        else:
            kwargs["channel"] = "chrome"
        self.ctx = run.pw.chromium.launch_persistent_context(**kwargs)
        self.ctx.set_default_timeout(20000)
        self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()

    def restart(self):
        """The browser closes and starts again on the same profile, with what it keeps on disk."""
        self.ctx.close()
        self._launch()

    def login(self):
        p = self.page
        p.goto("/login")
        if "/login" not in p.url:
            return
        p.fill("#username", ADMIN)
        p.fill("#password", self.run.stack.password)
        p.click("button[type=submit]")
        p.wait_for_url(lambda url: "/login" not in url)

    def logout(self):
        p = self.page
        if not p.locator("#logout-form").count():
            p.goto(OVERVIEW)
        with p.expect_navigation():
            p.evaluate("document.getElementById('logout-form').submit()")
        p.wait_for_url("**/login**")

    def goto(self, page, url):
        page.goto(url)
        if "/login" in page.url:  # a session the browser no longer has: sign in as a user would
            self.login()
            page.goto(url)

    # The Overview

    def overview(self, page=None):
        p = page or self.page
        self.goto(p, OVERVIEW)
        p.wait_for_function("() => typeof OverviewTable !== 'undefined'"
                            " && OverviewTable.data().count() > 0")
        return p

    def shown(self, page=None):
        return (page or self.page).evaluate(
            "() => Array.from(document.querySelectorAll("
            "'#overview_table thead tr:not(.filters) th')).map(th => th.textContent.trim())")

    def count(self):
        return self.page.evaluate("() => OverviewTable.rows({search: 'applied'}).count()")

    def has_control(self, timeout=5000):
        try:
            self.page.locator(CONTROL).first.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    def open_control(self):
        p = self.page
        if not p.locator(ITEMS).first.is_visible():
            expect(self.has_control(), "the Overview has no control titled 'Toggle columns'")
            p.locator(CONTROL).first.click()
            p.locator(ITEMS).first.wait_for(state="visible", timeout=5000)
        return p.locator(ITEMS)

    def close_control(self):
        p = self.page
        if p.locator(ITEMS).first.is_visible():
            p.keyboard.press("Escape")  # Buttons closes the list, fading it out
            p.locator(ITEMS).first.wait_for(state="hidden", timeout=5000)

    def toggle(self, title):
        before = self.shown()
        items = self.open_control()
        items.filter(has_text=re.compile(r"^\s*%s\s*$" % re.escape(title))).first.click()
        self.page.wait_for_function("b => Array.from(document.querySelectorAll("
                                    "'#overview_table thead tr:not(.filters) th')).length"
                                    " !== b", arg=len(before))
        self.close_control()

    def default_columns(self):
        self.open_control()
        self.page.locator(COLLECTION + " .dt-button").filter(has_text="Default columns").first.click()
        self.page.wait_for_timeout(300)
        self.close_control()

    def filter_field(self, title):
        index = self.shown().index(title)
        return self.page.locator("#overview_table thead tr.filters th").nth(index)

    def set_filter(self, title, text):
        field = self.filter_field(title).locator("input")
        field.fill("")
        field.press_sequentially(text)
        self.page.wait_for_timeout(300)

    # The notes page

    def notes(self, note_id):
        p = self.page
        self.goto(p, NOTES)
        self.open_note(note_id)
        return p

    def open_note(self, note_id):
        p = self.page
        p.locator("#note-%d > a" % note_id).first.click()
        p.wait_for_function("n => (document.getElementById('currentNoteIDLabel').textContent"
                            " || '').startsWith('#' + n + ' ')", arg=note_id)
        p.wait_for_timeout(300)

    def editor(self):
        return self.page.locator("#container_note_content").is_visible()

    def view(self):
        return self.page.locator("#ctrd_notesum").is_visible()

    def round_button(self):
        self.page.click("button.icon-note")
        self.page.wait_for_timeout(400)

    def plain_layout(self):
        """The editor shown and not expanded, whatever the image does."""
        if not self.editor():
            self.round_button()
        if not self.view():
            self.page.click("#btn_max_editor")
            self.page.wait_for_timeout(300)

    def close(self):
        self.ctx.close()


class Run:
    def __init__(self, args, pw, work):
        self.args, self.pw, self.work = args, pw, work
        self.image = args.control or args.image
        self.old = args.control or args.old
        self.stack = Stack(work)
        self.results = []

    def check(self, tid, kind, text, fn):
        try:
            fn()
            ok, detail = True, ""
        except Exception as e:  # a check fails on any error, and the run goes on
            ok, detail = False, self.stack.redact(first_line(e))
        self.results.append((tid, kind, ok))
        print("%s [%s]%s %s %s%s" % ("ok  " if ok else "FAIL", kind, " " if kind == "new" else "",
                                     tid, text, "" if ok else ": " + detail), flush=True)

    def setup(self):
        api = self.stack.api
        ids = [api("POST", "/manage/cases/add", {
            "case_name": "iw2x case %02d" % i, "case_description": "iw2x check-ui",
            "case_customer": 1, "case_soc_id": "", "classification_id": 1,
            "severity_id": 1 + i % 6})["case_id"] for i in range(CASES)]
        for case_id in ids[:FALSE_POSITIVE]:
            api("POST", "/manage/cases/update/%d" % case_id, {"status_id": 1})
        for case_id in ids[-CLOSED:]:
            api("POST", "/manage/cases/close/%d" % case_id)
        self.directory = api("POST", NOTES.replace("/case/notes", "/case/notes/directories/add"),
                             {"name": "iw2x", "parent_id": None})["id"]
        self.note1, self.note2 = (api("POST", NOTES.replace("/case/notes", "/case/notes/add"), {
            "directory_id": self.directory, "note_title": "iw2x note %d" % n,
            "note_content": "# iw2x note %d\n\nThe text of note %d." % (n, n)})["note_id"]
            for n in (1, 2))

    def start_lines(self):
        """The app's lines of the defaults and its warnings, each as (level, message)."""
        lines = []
        for line in self.stack.app_log().splitlines():
            parts = line.split(" :: ", 4)
            if len(parts) == 5 and parts[4].startswith("iris-web-2x"):
                lines.append((parts[1], parts[4]))
        return ([l for l in lines if l[1].startswith("iris-web-2x defaults: ")],
                sorted(l for l in lines if l[1].startswith("iris-web-2x: ")))

    def expect_start_lines(self, line, warnings):
        defaults, found = self.start_lines()
        expect(defaults == [("INFO", line)], "the start log has %d line(s) of the defaults%s"
               % (len(defaults), ", not this one: " + defaults[0][1] if len(defaults) == 1 else ""))
        want = sorted(("WARNING", w) for w in warnings)
        expect(found == want, ("the start log has %d warning(s), not %d" % (len(found), len(want)))
               if len(found) != len(want) else
               "the start log's warnings differ: %s" % [m for _, m in found])

    # Phase 1: --old. The first profile has loaded both pages; it restarts and loads them again.

    def t2(self):
        a, stack = self.a, self.stack
        served = sorted({s for l in stack.access_log() for s in SCRIPTS
                         if '"GET %s' % s in l and '" 200 ' in l})
        expect(served == sorted(SCRIPTS), "nginx logged %s on the first loads, not both scripts"
               % (served or "none"))
        a.restart()
        mark = len(stack.access_log())
        a.overview()
        a.notes(self.note1)
        lines = stack.access_log()[mark:]
        pages = [l for l in lines if '"GET %s ' % OVERVIEW in l or '"GET %s' % NOTES in l]
        asked = sorted({s for l in lines for s in SCRIPTS if '"GET %s' % s in l})
        expect(len(pages) >= 2, "nginx logged no second load of the pages")
        expect(not asked, "after the restart the browser asked nginx again for %s" % ", ".join(asked))

    # Phase 2: the image under test, no variable.

    def t1(self):
        a = self.a
        a.overview()
        expect(a.shown() == STOCK, "the Overview shows %s" % a.shown())
        a.notes(self.note1)
        expect(a.editor(), "a note opens with its editor hidden")

    def t3(self):
        a = self.a
        a.overview()
        items = a.open_control()
        texts = [t.strip() for t in items.all_inner_texts()]
        marked = items.evaluate_all(  # what the user sees, not only a class
            "els => els.map(e => { const b = getComputedStyle(e, '::before');"
            " return b.visibility === 'visible' && !['none', 'normal', '\"\"'].includes(b.content); })")
        a.close_control()
        expect(texts == TOGGLED, "the control lists %s" % texts)
        want = [t in a.shown() for t in TOGGLED]
        expect(marked == want, "the control marks %s as shown" % [t for t, x in zip(texts, marked) if x])

    def t4(self):
        a = self.a
        want = [t for t in TITLES if t == "Outcome" or (t in STOCK and t != "Owner")]
        a.overview()
        a.toggle("Outcome")
        a.toggle("Owner")
        expect(a.shown() == want, "after the toggles the Overview shows %s" % a.shown())
        a.overview()
        expect(a.shown() == want, "after a reload the Overview shows %s" % a.shown())
        tab = a.ctx.new_page()
        try:
            a.overview(tab)
            expect(a.shown(tab) == want, "a new tab shows %s" % a.shown(tab))
        finally:
            tab.close()
        a.logout()
        a.login()
        a.overview()
        expect(a.shown() == want, "after signing out and in the Overview shows %s" % a.shown())

    def t5(self):
        a, d = self.a, self.d
        a.overview()
        a.default_columns()
        expect(a.shown() == STOCK, "Default columns shows %s" % a.shown())
        a.overview()
        expect(a.shown() == STOCK, "after a reload the Overview shows %s" % a.shown())
        # A choice made and then forgotten, which T13 tells apart from a choice kept.
        d.overview()
        d.toggle("Owner")
        d.default_columns()
        expect(d.shown() == STOCK, "in a second profile Default columns shows %s" % d.shown())

    def t6(self):
        a = self.a
        a.overview()
        everything = a.count()
        a.toggle("Outcome")
        expect(a.filter_field("Outcome").locator("input").count() == 1,
               "the column shown later has no filter field")
        a.set_filter("Outcome", "false")
        expect(a.count() == FALSE_POSITIVE, "its field filters %d rows, not %d" % (a.count(), FALSE_POSITIVE))
        a.set_filter("Title", "iw2x")
        a.filter_field("Outcome").locator("i.fa-times-circle").click()
        a.page.wait_for_timeout(300)
        state = a.page.evaluate("() => [OverviewTable.column(0).search(), OverviewTable.column(3).search()]")
        expect(a.filter_field("Outcome").locator("input").input_value() == "" and state[0] == "",
               "its clear button leaves it filtering")
        expect(a.filter_field("Title").locator("input").input_value() == "iw2x" and state[1] != "",
               "its clear button also cleared Title's field")
        a.filter_field("Title").locator("i.fa-times-circle").click()
        a.set_filter("Outcome", "false")
        a.toggle("Outcome")
        search = a.page.evaluate("() => OverviewTable.column(0).search()")
        expect(search == "" and a.count() == everything,
               "hiding it keeps its filter (%d of %d rows)" % (a.count(), everything))
        a.toggle("Outcome")
        field = a.filter_field("Outcome").locator("input").input_value()
        a.toggle("Outcome")
        expect(field == "", "shown again, its field holds %r" % field)

    def t7(self):
        a = self.a
        p = a.overview()
        expect(a.shown() == STOCK, "the Overview shows %s" % a.shown())
        open_rows = a.count()
        expect(open_rows >= 26, "only %d open cases" % open_rows)
        a.set_filter("Title", "iw2x case 07")
        expect(a.count() == 1, "Title's field filters %d rows" % a.count())
        a.set_filter("Customer", "Iris")
        a.filter_field("Title").locator("i.fa-times-circle").click()
        p.wait_for_timeout(300)
        expect(a.count() == open_rows and a.filter_field("Customer").locator("input").input_value() == "Iris",
               "Title's clear button left %d rows or cleared Customer's field" % a.count())
        a.filter_field("Customer").locator("i.fa-times-circle").click()
        p.locator("#overview_table thead tr:not(.filters) th").filter(has_text="Title").first.click()
        try:  # with processing on, DataTables sorts after a timeout of its own
            p.wait_for_function("() => OverviewTable.order()[0][0] === 3", timeout=5000)
        except Exception:
            pass
        order = p.evaluate("() => [OverviewTable.order()[0], OverviewTable.rows({order: 'current',"
                           " page: 'current'}).data().toArray().map(r => r.case_id)]")
        expect(order[0][0] == 3 and order[1] == sorted(order[1]), "sorting by Title gave %s" % order[0])
        p.locator("#overview_table_paginate .paginate_button.next").first.click()
        expect(p.evaluate("() => OverviewTable.page()") == 1, "paging stayed on the first page")
        p.locator("#table_buttons .dtsb-add").first.click()
        p.locator(".dtsb-criteria").first.wait_for(state="visible")
        p.locator(".btn-quick-view").first.click()
        p.locator("#caseViewModal").wait_for(state="visible")
        expect(p.locator("#caseViewModal .modal-title").inner_text().strip() != "",
               "the quick view has no title")
        p.keyboard.press("Escape")
        p.locator("#caseViewModal").wait_for(state="hidden")
        a.overview()
        p.get_by_text("Show closed cases").first.click()
        p.wait_for_function("n => OverviewTable.data().count() === n", arg=open_rows + CLOSED)
        expect(p.locator("#overviewTableTitle").inner_text().strip() == "All cases",
               "the switch did not show all cases")
        expect(not p.locator(".buttons-csv, .buttons-copy, .buttons-html5").count()
               and not p.locator("#table_buttons").get_by_text("Export", exact=True).count()
               and not p.locator("#table_buttons").get_by_text("Copy", exact=True).count(),
               "the Overview has Export or Copy")
        p.locator("#overview_table tbody tr").first.locator("td").nth(2).click()
        expect(not p.locator("#overview_table tbody tr.selected").count(), "a click selects a row")
        # Responsive collapses the table when the window narrows, not when the page loads
        # into a narrow window, where the table scrolls instead: 2.4.29 does both.
        a.overview()
        p.set_viewport_size({"width": 560, "height": 900})
        try:
            p.wait_for_selector("#overview_table.collapsed")
            p.locator("#overview_table tbody tr").first.locator("td").first.click(position={"x": 8, "y": 8})
            details = p.locator("#overview_table tbody tr.child .dtr-details")
            details.first.wait_for(state="visible")
            titles = [t.strip().rstrip(":") for t in details.first.locator("tr td:first-child").all_inner_texts()]
            expect(titles == TITLES, "the details row lists %s" % titles)
        finally:
            p.set_viewport_size({"width": 1920, "height": 1080})

    def t8(self):
        a = self.a
        a.notes(self.note1)
        a.plain_layout()
        a.round_button()
        expect(not a.editor(), "the round button did not hide the editor")
        a.open_note(self.note2)
        expect(not a.editor(), "another note opens with its editor")
        a.page.reload()
        a.page.wait_for_function("n => (document.getElementById('currentNoteIDLabel').textContent"
                                 " || '').startsWith('#' + n + ' ')", arg=self.note2)
        a.page.wait_for_timeout(300)
        expect(not a.editor(), "after a reload the note opens with its editor")
        a.logout()
        a.login()
        a.notes(self.note1)
        expect(not a.editor(), "after signing out and in the note opens with its editor")
        a.round_button()
        a.notes(self.note2)
        expect(a.editor(), "shown again, the editor is hidden after a reload")
        a.logout()
        a.login()
        a.notes(self.note1)
        expect(a.editor(), "shown again, the editor is hidden after signing out and in")

    def t9(self):
        a = self.a
        p = a.notes(self.note1)
        a.plain_layout()
        a.round_button()
        p.locator("#directory-%d > a" % self.directory).first.click(button="right")
        p.locator(".dropdown-menu.show").get_by_text("Add note", exact=True).first.click()
        p.wait_for_function("n => { const t = document.getElementById('currentNoteIDLabel').textContent"
                            " || ''; return t.startsWith('#') && !t.startsWith('#' + n + ' '); }",
                            arg=self.note1)
        p.wait_for_timeout(500)
        expect(a.editor(), "the created note opens with its editor hidden")
        a.open_note(self.note2)
        expect(not a.editor(), "the next note opened has its editor shown")

    def t10(self):
        a = self.a
        p = a.notes(self.note1)
        a.plain_layout()
        p.click("#btn_max_editor")
        p.wait_for_timeout(300)
        expect(not a.view(), "the expansion did not hide the view")
        a.round_button()
        expect(a.view(), "hiding the expanded editor leaves the view hidden")
        view, row = p.locator("#ctrd_notesum").bounding_box(), p.locator("#noteContentScroll").bounding_box()
        expect(view["width"] >= 0.8 * row["width"],
               "the view takes %d of %d pixels" % (view["width"], row["width"]))

    def t11(self):
        a, d = self.a, self.d
        a.notes(self.note1)
        a.plain_layout()
        d.notes(self.note1)
        d.plain_layout()
        d.round_button()
        expect(not d.editor(), "the second session's editor is shown")
        mark = "iw2x-relay-" + secrets.token_hex(4)
        a.page.click("#editor_detail .ace_content")
        a.page.keyboard.press("Control+End")
        a.page.keyboard.type(" " + mark)
        a.page.keyboard.press("Control+s")
        deadline = time.time() + 15
        while mark not in self.stack.api("GET", "/case/notes/%d?cid=1" % self.note1)["note_content"]:
            expect(time.time() < deadline, "typing did not save the note")
            time.sleep(1)
        d.page.wait_for_function("m => document.getElementById('targetDiv').textContent.includes(m)",
                                 arg=mark, timeout=15000)
        a.page.click("a[onclick='load_note_revisions()']")
        a.page.locator("#noteModificationHistoryModal").wait_for(state="visible")
        revisions = a.page.locator("#revisionList li").count()
        a.page.keyboard.press("Escape")
        expect(revisions >= 2, "the note's history lists %d revision(s)" % revisions)

    def t12(self):
        self.expect_start_lines(LINE_STOCK, [])

    # Phase 3: the variables of T13.

    def t13(self):
        b, d, a = self.b, self.d, self.a
        b.overview()
        expect(b.shown() == T13_SHOWN, "a profile without a choice gets %s" % b.shown())
        b.notes(self.note1)
        expect(not b.editor(), "a profile without a choice gets the editor shown")
        d.overview()
        expect(d.shown() == T13_SHOWN, "the profile that pressed Default columns gets %s" % d.shown())
        a.overview()
        expect(a.shown() == STOCK, "the profile with a choice gets %s" % a.shown())
        a.notes(self.note1)
        expect(a.editor(), "the profile with a choice gets the editor hidden")
        self.expect_start_lines(LINE_T13, [])

    def t14(self):
        """Choices that 2.4.29 shows nothing of, so that T16 means something."""
        a = self.a
        want = [t for t in TITLES if t == "Outcome" or t in STOCK]
        a.overview()
        a.toggle("Outcome")
        a.notes(self.note1)
        a.plain_layout()
        a.round_button()
        a.overview()
        expect(a.shown() == want, "after a reload the Overview shows %s" % a.shown())
        a.notes(self.note1)
        expect(not a.editor(), "after a reload a note opens with its editor")

    # Phase 4: the variables of T15.

    def t15(self):
        c = self.c
        c.overview()
        expect(c.shown() == STOCK, "the Overview shows %s" % c.shown())
        c.notes(self.note1)
        expect(c.editor(), "a note opens with its editor hidden")
        self.expect_start_lines(LINE_STOCK, [WARN_COLUMNS, WARN_EDITOR])

    # Phase 5: back to --old, with the variables of T13.

    def t16(self):
        a = self.a
        a.overview()
        expect(not a.has_control(3000), "the Overview has the control")
        expect(a.shown() == STOCK, "the Overview shows %s" % a.shown())
        a.notes(self.note1)
        expect(a.editor(), "a note opens with its editor hidden")

    def main(self):
        stack = self.stack
        print("-- %s, the stock database and nginx; cases and notes" % self.old, flush=True)
        stack.start(self.old)
        self.setup()
        self.a = Profile(self, "a")
        self.a.overview()
        self.a.notes(self.note1)
        self.check("T2", "same", "the first loads fetch both scripts; after a restart, the disk cache serves them", self.t2)

        print("-- swap to %s, no variable" % self.image, flush=True)
        stack.swap(self.image)
        self.check("T1", "same", "no variable, no choice: the columns of 2.4.29, a note with its editor", self.t1)
        self.check("T3", "new", "the control lists the eleven columns but Title, marked as shown", self.t3)
        self.check("T4", "new", "a choice stays after a reload, in a new tab, after signing out and in", self.t4)
        self.d = Profile(self, "d")
        self.check("T5", "new", "Default columns brings back the defaults, and a reload keeps them", self.t5)
        self.check("T6", "new", "a column shown later has its own filter field; hiding it empties it", self.t6)
        self.check("T7", "same", "filters, sorting, paging, SearchBuilder, all cases, quick view, details row", self.t7)
        self.check("T8", "new", "the editor's choice holds for another note, a reload, signing out and in", self.t8)
        self.check("T9", "new", "a created note opens with its editor; the next note takes the choice", self.t9)
        self.check("T10", "new", "hiding the expanded editor leaves the view shown, across the width", self.t10)
        self.check("T11", "same", "saving, a second session rendering the change, the note's history", self.t11)
        self.check("T12", "new", "the start log names the defaults of 2.4.29, once, with no warning", self.t12)

        print("-- %s with %s" % (self.image, " ".join("%s=%s" % kv for kv in T13_ENV.items())), flush=True)
        stack.swap(self.image, T13_ENV)
        self.b = Profile(self, "b")
        self.check("T13", "new", "the variables set the defaults, also after Default columns; a choice keeps", self.t13)
        self.check("T14", "new", "before the way back the first profile keeps Outcome shown, the editor hidden", self.t14)
        self.b.close()
        self.d.close()

        print("-- %s with %s" % (self.image, " ".join("%s=%s" % kv for kv in T15_ENV.items())), flush=True)
        stack.swap(self.image, T15_ENV)
        self.c = Profile(self, "c")
        self.check("T15", "new", "unusable values: the defaults of 2.4.29, exactly two warnings and the line", self.t15)
        self.c.close()

        print("-- back to %s, still with the variables of T13" % self.old, flush=True)
        stack.swap(self.old, T13_ENV)
        self.check("T16", "same", "after the way back: no control, the columns and editor of 2.4.29", self.t16)
        self.a.close()
        return self.verdict()

    def verdict(self):
        new = [ok for _, kind, ok in self.results if kind == "new"]
        same = [ok for _, kind, ok in self.results if kind == "same"]
        if not self.args.control:
            failed = [tid for tid, _, ok in self.results if not ok]
            print("%d check(s) failed" % len(failed) if failed else "all checks passed")
            return 1 if failed else 0
        good = not any(new) and all(same)
        print("%s control: %d of %d [new] check(s) fail and %d of %d [same] check(s) pass on %s"
              % ("ok  " if good else "FAIL", new.count(False), len(new), same.count(True), len(same),
                 self.image))
        return 0 if good else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("image", nargs="?")
    parser.add_argument("--old", help="the image before the swap and after the way back")
    parser.add_argument("--control", metavar="IMAGE", help="run on IMAGE as both images")
    parser.add_argument("--browser", help="a Chromium-family browser instead of Google Chrome")
    args = parser.parse_args()
    if bool(args.control) == bool(args.image and args.old) or (args.control and (args.image or args.old)):
        parser.error("give <image> --old <image>, or --control <image>")
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    work = Path(tempfile.mkdtemp(prefix="iw2x-ui-"))
    run = None
    try:
        with sync_playwright() as pw:
            run = Run(args, pw, work)
            return run.main()
    except Exception as e:
        text = run.stack.redact(str(e)) if run else str(e)
        print("FAIL the run stopped: %s" % text.strip())
        return 1
    finally:
        if run:
            run.stack.cleanup()
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
