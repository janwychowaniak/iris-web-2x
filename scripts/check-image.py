#!/usr/bin/env python3
"""The image checks of CI that need no database: packages, filesystem, labels and
configuration, the templates of the attribute tab buttons, the versioned names of the patched
scripts, and the copy of IRIS's filter the tests use. The image is compared with the base its
Dockerfile names.

    check-image.py <image> [--revision <commit>]
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
from itertools import count

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = "/opt/venv/lib/python3.9/site-packages"
DOC = "/usr/share/doc/iris-web-2x"
PACKAGES = {"iris_webhooks_module": "1.0.9+jw.2", "iris_facade_renderer_module": "0.2.0"}
RENDERER_FILES = ["__init__.py", "IrisFacadeRendererConfig.py",
                  "IrisFacadeRendererInterface.py", "render.py"]
DOC_FILES = ["VERSION", "LICENSE", "COPYING", "NOTICE"]
CONFIG_KEYS = ["Entrypoint", "Cmd", "WorkingDir", "Env", "User", "ExposedPorts", "Volumes",
               "StopSignal", "Healthcheck", "OnBuild", "Shell"]


def patched_files():
    """{path in the image: patched sha256}, from patches/patched.sha256."""
    out = {}
    for line in (ROOT / "patches/patched.sha256").read_text().splitlines():
        digest, path = line.split(None, 1)
        out["/iriswebapp/" + path] = digest
    return out


PATCHED = patched_files()
ALLOWED = re.compile(
    "^(?:%s|%s/(?:%s)(?:/.*|-[^/]+\\.dist-info(?:/.*)?)?|%s(?:/.*)?)$"
    % ("|".join(map(re.escape, PATCHED)), re.escape(SITE),
       "|".join(map(re.escape, PACKAGES)), re.escape(DOC)))

failures = []
_names = count()


def check(ok, name, detail=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok or not detail else ": " + detail))
    if not ok:
        failures.append(name)


def docker(*args, stdin=None):
    return subprocess.run(["docker", *args], input=stdin, check=True,
                          capture_output=True).stdout.decode()


def run_in(image, entrypoint, *args, stdin=None):
    """Run a command in a throwaway container of the image, without network."""
    return docker("run", "--rm", "-i", "--name", "iw2x-check-%d-%d" % (os.getpid(), next(_names)),
                  "--network", "none", "--env", "PYTHONDONTWRITEBYTECODE=1",
                  "--entrypoint", entrypoint, image, *args, stdin=stdin)


def inventory(image):
    script = (ROOT / "scripts/inventory.py").read_bytes()
    entries = {}
    for line in run_in(image, "python3", "-I", "-B", "-", stdin=script).splitlines():
        path, *rest = line.split("\t")
        entries[path] = tuple(rest)  # kind, mode, owner, size, sha256 or link target
    return entries


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_packages(base, image):
    versions = run_in(image, "python", "-c",
                      "import importlib.metadata as m, sys\n"
                      "for p in sys.argv[1:]:\n"
                      "    try:\n        print(m.version(p))\n"
                      "    except m.PackageNotFoundError:\n        print('-')", *PACKAGES).split()
    check(versions == list(PACKAGES.values()), "package versions %s" % " ".join(PACKAGES.values()),
          "got %s" % " ".join(versions))

    def freeze(img):
        return set(run_in(img, "pip", "freeze", "--all").splitlines())

    def name(line):
        return re.split(r"[ =@]", line, 1)[0]

    before, after = freeze(base), freeze(image)
    removed = sorted(name(l) for l in before - after)
    added = sorted(name(l) for l in after - before)
    check(removed == ["iris_webhooks_module"] and added == sorted(PACKAGES),
          "pip freeze differs from the base's in the two packages only",
          "removed %s, added %s" % (removed, added))

    dpkg = ["dpkg-query", "-W", "-f", "${Package} ${Version} ${Architecture}\n"]
    check(run_in(base, *dpkg) == run_in(image, *dpkg), "Debian packages identical to the base's")


def check_filesystem(base, image):
    b, i = inventory(base), inventory(image)
    differing = sorted(p for p in set(b) | set(i) if b.get(p) != i.get(p))
    outside = [p for p in differing if not ALLOWED.match(p)]
    check(not outside, "filesystem differs from the base's only in the image's own changes (%d entries)"
          % len(differing), "%d outside, first: %s" % (len(outside), outside[:5]))

    for path, digest in PATCHED.items():
        ok = (path in b and path in i and b[path][:3] == i[path][:3]
              and i[path][0] == "f" and i[path][4] == digest)
        check(ok, "%s patched, mode and owner kept" % path,
              "base %s, image %s" % (b.get(path), i.get(path)))

    doc = {p: e for p, e in i.items() if p == DOC or p.startswith(DOC + "/")}
    want = {DOC: ("d", "755", "0:0")}
    want.update({"%s/%s" % (DOC, f): ("f", "644", "0:0", str((ROOT / f).stat().st_size), sha256(ROOT / f))
                 for f in DOC_FILES})
    check({p: e[:len(want[p])] if p in want else e for p, e in doc.items()} == want,
          "%s holds %s, mode 644, equal to the repository's" % (DOC, ", ".join(DOC_FILES)))

    pkg = SITE + "/iris_facade_renderer_module"
    files = sorted(p[len(pkg) + 1:] for p, e in i.items() if p.startswith(pkg + "/") and e[0] == "f")
    want_files = sorted(RENDERER_FILES + ["__pycache__/%s.cpython-39.pyc" % f[:-3] for f in RENDERER_FILES])
    check(files == want_files, "the renderer package holds its four files and their bytecode only",
          "got %s" % files)
    src = ROOT / "renderer/iris_facade_renderer_module"
    same = all(i.get("%s/%s" % (pkg, f), ("",) * 5)[4] == sha256(src / f) for f in RENDERER_FILES)
    check(same, "the renderer's installed files equal renderer/iris_facade_renderer_module/")


def check_labels_and_config(base, image, revision):
    def config(img):
        return json.loads(docker("image", "inspect", "--format", "{{json .Config}}", img))

    c = config(image)
    labels = c.get("Labels") or {}
    base_digest = re.search(r"^FROM \S+@(sha256:[0-9a-f]{64})$",
                            (ROOT / "Dockerfile").read_text(), re.M).group(1)
    want = {
        "org.opencontainers.image.version": (ROOT / "VERSION").read_text().strip(),
        "org.opencontainers.image.source": "https://github.com/janwychowaniak/iris-web-2x",
        "org.opencontainers.image.licenses": "LGPL-3.0-or-later",
        "org.opencontainers.image.base.name": "ghcr.io/dfir-iris/iriswebapp_app:v2.4.29",
        "org.opencontainers.image.base.digest": base_digest,
        "org.opencontainers.image.title": "iris-web-2x",
        "org.opencontainers.image.url": "https://github.com/janwychowaniak/iris-web-2x",
        "org.opencontainers.image.description":
            "DFIR-IRIS 2.4.29 with two upstream worker fixes and two modules built in",
    }
    got = {k: v for k, v in labels.items() if k in want}
    check(got == want, "the image's labels",
          "differ: %s" % sorted(k for k in want if labels.get(k) != want[k]))
    extra = set(labels) - set(want) - {"org.opencontainers.image.revision",
                                         "org.opencontainers.image.created"}
    check(not extra, "no label besides the image's own", "others: %s" % sorted(extra))
    rev = labels.get("org.opencontainers.image.revision", "")
    check(rev == revision if revision else bool(rev), "label revision %s" % (revision or "set"),
          "got %r" % rev)
    created = labels.get("org.opencontainers.image.created", "")
    check(bool(re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?(Z|[+-]\d\d:\d\d)$", created)),
          "label created is a timestamp", "got %r" % created)

    b = config(base)
    differ = [k for k in CONFIG_KEYS if c.get(k) != b.get(k)]
    check(not differ, "entrypoint, command, working directory, environment and user are the base's",
          "differ: %s" % differ)


# The tab names whose button opens its pane on the stock templates of 2.4.29, under its
# Bootstrap 4.6.2: only the new-case modal's ids start with a letter, and they hold only
# while the name has no punctuation.
STOCK_OPENS = {"shared nav": [], "case info": [],
               "new case": ["VT Report", "1 leading digit", "Zażółć gęślą jaźń"]}


def check_templates(base, image):
    script = (ROOT / "scripts/check-templates.py").read_bytes()
    b, i = (json.loads(run_in(img, "python", "-", stdin=script)) for img in (base, image))

    def opens(results):
        return {t: [r["name"] for r in rows if r["resolves"] == r["pane"]] for t, rows in results.items()}

    names = {t: [r["name"] for r in rows] for t, rows in i.items()}
    check(opens(i) == names, "every attribute tab button opens its own pane (%d templates, %d names)"
          % (len(names), len(next(iter(names.values())))), "opening: %s" % opens(i))
    check(opens(b) == STOCK_OPENS, "control: on the stock templates, the same check rejects what a browser rejects",
          "stock opening: %s" % opens(b))
    same = all((rb["button"], rb["text"], rb["pane"]) == (ri["button"], ri["text"], ri["pane"])
               for t in b for rb, ri in zip(b[t], i[t]))
    check(same, "the buttons differ from the stock ones by data-target alone, the panes not at all")


# The scripts the change patches. A page names each with a "v" (SPEC.md §7): the stock nginx
# lets a browser keep /static for a year, so a changed script under an unchanged URL would stay
# unseen after the swap, and a cached one would follow the way back.
VERSIONED = ("assets/js/iris/overview.js", "assets/js/iris/case.notes.js")
SCRIPT_REFERENCES = r"""
import json, pathlib, re, sys
found = []
for path in sorted(pathlib.Path("/iriswebapp/app").rglob("*.html")):
    text = path.read_text(errors="replace")
    for m in re.finditer(r"assets/js/iris/(?:overview|case\.notes)\.js(\?v=[^\"'\s]+)?", text):
        found.append([str(path.relative_to("/iriswebapp")), m.group(0)])
print(json.dumps(found))
"""
STOCK_REFERENCES = [["app/blueprints/case/templates/case_notes_v2.html", "assets/js/iris/case.notes.js"],
                    ["app/blueprints/overview/templates/overview.html", "assets/js/iris/overview.js"]]


def check_versioned_scripts(base, image):
    def references(img):
        return json.loads(run_in(img, "python3", "-I", "-B", "-", stdin=SCRIPT_REFERENCES.encode()))

    b, i = references(base), references(image)
    bare = [r for r in i if "?v=" not in r[1]]
    named = sorted({r[1].split("?")[0] for r in i})
    check(named == sorted(VERSIONED) and not bare,
          "no template names overview.js or case.notes.js without a v (%d reference(s))" % len(i),
          "without one: %s; named: %s" % (bare, named))
    check(sorted(b) == STOCK_REFERENCES,
          "control: on the base, the same check finds the two references without a v",
          "found %s" % b)


def check_filter_copy(image):
    copy = (ROOT / "renderer/tests/iris_2429_filter.py").read_text()
    block = copy[copy.index("_ATTR_HTML_ALLOWED_TAGS = ["):]
    source = run_in(image, "cat", "/iriswebapp/app/__init__.py")
    check(block in source, "the tests' copy of the filter equals the image's")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("image")
    parser.add_argument("--revision", help="the commit the image must name")
    args = parser.parse_args()
    base = re.search(r"^FROM (\S+)$", (ROOT / "Dockerfile").read_text(), re.M).group(1)
    check_packages(base, args.image)
    check_filesystem(base, args.image)
    check_labels_and_config(base, args.image, args.revision)
    check_templates(base, args.image)
    check_versioned_scripts(base, args.image)
    check_filter_copy(args.image)
    print("%d check(s) failed" % len(failures) if failures else "all checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
