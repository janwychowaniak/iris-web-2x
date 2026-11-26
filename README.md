# iris-web-2x

DFIR-IRIS 2.4.29 with two upstream worker fixes backported and two modules built in.

`ghcr.io/janwychowaniak/iris-web-2x:2.4.29-N` is the stock DFIR-IRIS application image,
`ghcr.io/dfir-iris/iriswebapp_app:v2.4.29`, plus seven things and nothing else:

- two fixes for the Celery worker, taken from the IRIS 3.x backend;
- a fix of 2.4.29's attribute tab buttons, which open nothing under its own Bootstrap;
- a fix of 2.4.29's start, whose database migration disables the loggers that exist at that
  moment, Celery's and gunicorn's among them;
- the Overview's columns and a note's editor, shown or hidden by each user and remembered in
  the browser, with the defaults set by the deployment;
- the IrisFacadeRenderer module 0.2.0, built from this repository;
- a fork of the IrisWebHooks module, `1.0.9+jw.2`, in place of the stock 1.0.9;
- the image's own version, in labels, in a file and in the start log.

It runs the web application and the Celery worker exactly as the stock image does, from
the same compose file. nginx and the database stay the stock 2.4.29 images. The image is
built for linux/amd64, on the stock image pinned by digest:
`ghcr.io/dfir-iris/iriswebapp_app@sha256:d7d23026bdde593278075821d3abc8649fe28d618d5784cc9875bd7a3d05699b`.

## Why

IRIS 2.4.29 is the last release of the 2.x line, and the 3.x line is in beta. Two gaps of
the stock image stay open on 2.4.29:

- **The worker.** Its prefork pool forks the children from a parent that has already
  opened its database connections. The stock guard, a `task_prerun` handler, needs an
  application context that is pushed only after the signal, so it fails on every task.
  Hook tasks running at the same time in different children then share one connection.
  Upstream fixed this in the 3.x backend only.
- **The modules.** A module installed into running containers with pip is lost at the
  next container recreate, while its registration and hooks stay in the database. Built
  into the image, the modules survive.

## The changes to IRIS

Twelve files of IRIS change; each patch is in [`patches/`](patches), and the build checks
every file's sha256 before and after patching.

| File, under `/iriswebapp` | Change | Origin |
|---|---|---|
| `app/iris_engine/module_handler/module_handler.py` | at the entry of `task_hook_wrapper`, `db.session.remove()` and `db.engine.dispose()` | [`dfir-iris/iris-backend` `294ed4a1`](https://github.com/dfir-iris/iris-backend/commit/294ed4a19bf7cfe60c75f20cacdbc79d91ce6a9f) |
| `app/iris_engine/tasker/tasks.py` | the `task_prerun` handler becomes a `worker_process_init` handler that discards the inherited pool with `db.engine.dispose(close=False)` inside an application context | [`dfir-iris/iris-backend` `9098c754`](https://github.com/dfir-iris/iris-backend/commit/9098c754089d28e9ebe448fb37a9ae55403b8b7e), its change to this file only |
| `iris-entrypoint.sh` | the start line (below) | this repository |
| `app/templates/modals/modal_attributes_nav.html`, `app/blueprints/manage/templates/modal_case_info_from_case.html`, `app/blueprints/manage/templates/modal_add_case.html` | each attribute tab button names its pane in a `data-target` (below) | this repository |
| `app/alembic/env.py` | its `fileConfig` call passes `disable_existing_loggers=False`, so the loggers that exist when the migration configures logging stay enabled (below) | this repository |
| `app/configuration.py` | reads `IW2X_OVERVIEW_COLUMNS` and `IW2X_NOTE_EDITOR` at start; the app's start log names the defaults in effect | this repository |
| `app/blueprints/overview/templates/overview.html`, `app/static/assets/js/iris/overview.js` | the Overview's column control and the choice it makes | this repository |
| `app/blueprints/case/templates/case_notes_v2.html`, `app/static/assets/js/iris/case.notes.js` | the choice to show or hide a note's editor, one for every note | this repository |

The two worker patches carry upstream's added and removed lines byte for byte, written
against the 2.4.29 files; CI proves it. The docstring of the second describes the 3.x
layout and stays as upstream wrote it: it refers to a gunicorn `post_fork` hook, which
2.4.29 does not have, and to `pool_pre_ping` in `app/db.py`, which 2.4.29 sets in
`app/__init__.py`.

**The attribute tab buttons.** In stock 2.4.29, the attribute tab buttons of the IOC,
asset, event, evidence, task, note, customer, attribute preview and case information
modals open nothing: they target a pane whose id starts with a digit (`#1_vt_report`),
which the Bootstrap 4.6.2 that 2.4.29 ships cannot select; the new-case modal's break the
same way on a tab name with punctuation. Each button now names its pane in a
`data-target` attribute selector, which holds any name; the panes and everything else in
the modals stay as they are.

**The loggers.** With `IRIS_WORKER` unset, as the upstream compose leaves it, IRIS's
post-init runs the database migration on every start of the app and of the worker.
Alembic's `env.py` then configures logging from `alembic.ini` with `fileConfig`, which by
default disables every existing logger outside those the file names and their children. In
stock 2.4.29 that silences, in the worker's pool children, Celery's lines on how each task
ended and on a signal handler that raised, and, in the gunicorn worker, gunicorn's error
log. The call now leaves those loggers enabled; the levels, handlers and formats it sets
stay as they were.

One ERROR comes with it at every start of the worker, after post-init:
`Signal handler <function setup_periodic_update_checks at 0x…> raised: TypeError("setup_periodic_update_checks() missing 1 required positional argument: 'self'")`,
with its traceback. It is IRIS 2.4.29's own fault, hidden until now by the disabled logger:
`app/iris_engine/updater/updater.py` connects that function to Celery's
`on_after_finalize` with a signature Celery cannot call, so the daily check for IRIS updates
is never scheduled at start. The image leaves it as it is.

## The Overview's columns and the notes editor

**The Overview.** A button with the column visibility icon, titled `Toggle columns`, under
`Add filter`, opens a menu of the table's columns but Title, which carries the case's link and
its quick view and stays shown. A check marks each column shown, and each entry shows or hides
its column; the last one, `Default columns`, brings back the defaults and forgets the choice. A column shown later comes with its filter
field; hiding a column empties its field and clears its filter, while SearchBuilder's criteria
stay as they are. Export, Copy and row selection stay absent, as in 2.4.29.

**The notes editor.** The round button beside `Save note` shows or hides a note's editor, as
in 2.4.29, and the choice now holds for every note: a note opens with its editor as the user
last left it, but for a note just created, which opens with it. Hiding the editor while it is
expanded ends the expansion, so that the rendered view takes the width.

**Where the choices live.** In the browser's storage for the IRIS site
(`iw2x.overview.columns`, `iw2x.notes.editor`), as IRIS keeps its own. They survive reloads,
new visits and signing out and in. Another browser or browser profile, another host name or
port for the same IRIS, a private window once it is closed, and clearing the site's data start
from the defaults; the users of one browser profile share its choices.

**The defaults.** Two variables of the app set them. With the upstream compose they go into
`.env`, which the compose passes to the app, and `docker compose up -d` applies a change. A
choice the user has made takes precedence over them.

| Variable | Value | Unset, empty or blank |
|---|---|---|
| `IW2X_OVERVIEW_COLUMNS` | the columns shown by default: identifiers separated by commas, in any order, spaces around them ignored; Title is shown whether listed or not | the columns 2.4.29 shows |
| `IW2X_NOTE_EDITOR` | `shown` or `hidden` | `shown` |

| Identifier | Column | Shown by 2.4.29 |
|---|---|---|
| `outcome` | Outcome | no |
| `case_id` | Case ID | no |
| `severity` | Severity | no |
| `title` | Title | always |
| `customer` | Customer | yes |
| `classification` | Classification | yes |
| `state` | State | yes |
| `tags` | Tags | yes |
| `open_since` | Open since | yes |
| `open_date` | Open date | yes |
| `tasks` | Tasks | yes |
| `owner` | Owner | yes |

A value the image cannot use, an identifier outside the table, commas and nothing else, or
anything but `shown` or `hidden` (letter case included), leaves the default of 2.4.29 for what
that variable sets. The app's start log names the defaults in effect, after one warning per
unusable value; the worker loads the same configuration and logs neither:

```
… :: WARNING :: configuration :: iw2x_ui_defaults :: iris-web-2x: IW2X_NOTE_EDITOR='maybe' cannot be used (expected 'shown' or 'hidden'); the default of 2.4.29 applies
… :: INFO :: configuration :: iw2x_ui_defaults :: iris-web-2x defaults: Overview columns title,customer,classification,state,tags,open_since,open_date,tasks,owner (2.4.29); note editor shown (2.4.29)
```

**The swap and the way back.** The stock nginx lets a browser keep `/static` for a year
without asking again, so the pages name the two patched scripts with a version
(`overview.js?v=2.4.29-3`, `case.notes.js?v=2.4.29-3`): a browser that used an earlier image
loads them at once, and after a way back it takes the earlier image's scripts from its cache
or from that image. The choices stay in the browser, unused by an earlier image, and apply
again after a later swap.

## The modules

### IrisFacadeRenderer 0.2.0

A processor module that renders the IOC field `ioc_enrichment`, a JSON object keyed by
service (`vt`, `abuseipdb`, `urlscan`), each value one answer of a reputation facade
(vt-proxy, abuseipdb-proxy) under their shared contract, ENVELOPE.md version 1. For each key
it writes one IOC attribute tab with one `html` field, on every IOC update and on the manual
trigger `Render facade reports`. It makes no outbound calls and holds no credentials.

| Value under a key | Badge |
|---|---|
| known, score above 0 | red: `score N/T`, with T the sum of the analysis stats; `score N` without them |
| known, score 0 or below | green: as above |
| not known, no record | grey: `unknown (no record)` |
| not known, with a record | grey: `no findings (score N)` |
| an error body | amber: `lookup failed (CODE)` |
| anything else | grey: `?`, and a warning in the task's log |

One bad value affects only its own tab. A tab IRIS fails to write, or a fault while
rendering, is logged and makes the task fail, while the other tabs and IOCs are written.

**The image does not register it.** Register and enable it in Manage → Modules (add
`iris_facade_renderer_module`, then enable it), or through the API:

```bash
curl -sX POST https://iris.example.net/manage/modules/add \
     -H "Authorization: Bearer $IRIS_API_KEY" -H 'Content-Type: application/json' \
     -d '{"module_name": "iris_facade_renderer_module"}'
# the answer's data.id is the module's id
curl -sX POST https://iris.example.net/manage/modules/enable/<id> \
     -H "Authorization: Bearer $IRIS_API_KEY"
```

These names stay fixed, so 0.2.0 replaces 0.1.1 in place on a database that registered
0.1.1, without registering it again: the import name `iris_facade_renderer_module`, the
module name `IrisFacadeRenderer`, interface version 1.2.0, the parameters
`frr_on_update_hook_enabled` and `frr_manual_hook_enabled`, the manual hook name, the tabs
`VT Report`, `AbuseIPDB Report`, `URLScan Report` and `<key> Report`, and the field
`HTML report`.

Manage → Modules shows the version stored when the module was registered, not the
installed one: a database that registered 0.1.1 keeps showing 0.1.1.

### IrisWebHooks 1.0.9+jw.2

The fork at
[`janwychowaniak/iris-webhooks-module`](https://github.com/janwychowaniak/iris-webhooks-module),
branch `init-user-case-id`, annotated tag `v1.0.9+jw.2` on commit `8b30028e`; its README
describes its three changes to the stock module. The build checks that the tag resolves to
that commit. The stock wheel stays in `/iriswebapp/dependencies/`.

On a fresh database IRIS registers the module itself, disabled, as one of its default
modules, and stores `1.0.9+jw.2`; a database that registered 1.0.9 keeps showing 1.0.9.

## Using it with the upstream compose

The upstream compose of 2.4.29 runs the app and the worker from the same two variables.
In its `.env`, set the first and add the second, which `.env.model` does not have:

```
APP_IMAGE_NAME=ghcr.io/janwychowaniak/iris-web-2x
APP_IMAGE_TAG=2.4.29-3
```

and recreate the containers with `docker compose up -d`. nginx and the database stay
stock. The variables of the defaults (above) go into the same `.env`.

**The way back** to the stock image is removing both lines and `docker compose up -d`
again. Disable the renderer in Manage → Modules first: the stock image does not have it,
while its registration and hooks stay in the database. The webhooks module goes back to
the stock 1.0.9. The users' column and editor choices stay in their browsers, unused by the
stock image.

## Reading the version

- **The labels:** `org.opencontainers.image.version` is the image's version, `.revision`
  the commit it was built from, `.base.digest` the stock image's digest:

  ```bash
  docker image inspect --format '{{json .Config.Labels}}' ghcr.io/janwychowaniak/iris-web-2x:2.4.29-3
  ```

- **The start log:** in both the app's and the worker's log, the entrypoint names the image,
  its version and the IRIS version of its base before gunicorn or Celery starts. In the
  worker's, the lines of `wait-for-iriswebapp.sh`, which the upstream compose runs first,
  come before it.

  ```
  iris-web-2x 2.4.29-3 (DFIR-IRIS v2.4.29)
  ```

- **The file:** `/usr/share/doc/iris-web-2x/VERSION`.

## Using a release file on a host without registry access

Every release on GitHub carries the published image as a file,
`iris-web-2x-<version>.tar.gz` (the image saved by its full tag, about 550 MB), with
`iris-web-2x-<version>.tar.gz.sha256` beside it. On the target host:

```bash
sha256sum -c iris-web-2x-2.4.29-3.tar.gz.sha256
docker load -i iris-web-2x-2.4.29-3.tar.gz
docker image inspect --format '{{.Id}}' ghcr.io/janwychowaniak/iris-web-2x:2.4.29-3
```

The last line must print the image Id (configuration digest) that
[`CHANGELOG.md`](CHANGELOG.md) records for the version. The Id survives the transfer where
the registry digest does not: on Docker's default `overlay2` image store it is the digest
of the image's configuration, which the archive carries byte for byte. Before it attaches
the file, the release workflow checks that the archive carries the configuration digest it
published, and loads the archive back into a store without the image.

The same Id can be checked without Docker: the archive's `manifest.json` names the
configuration blob, and that blob's SHA-256 is the Id.

```bash
config=$(tar -xzOf iris-web-2x-2.4.29-3.tar.gz manifest.json | grep -o '"Config":"[^"]*"' | cut -d'"' -f4)
tar -xzOf iris-web-2x-2.4.29-3.tar.gz "$config" | sha256sum   # the Id, without "sha256:"
```

The archive loads under `ghcr.io/janwychowaniak/iris-web-2x:2.4.29-3`, the name the two
compose variables above give, so `docker compose up -d` uses it without a pull.

## Building and checking

The Dockerfile builds with the classic builder. Each script below runs in CI
([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) on every push:

- `scripts/build.sh [<tag>]`: the build, with the labels' build arguments; the build itself
  checks the patches, the fork's tag and the version;
- `scripts/test-renderer.sh`: the renderer's tests, in the stock base image;
- `scripts/check-upstream-lines.py`: the worker patches against upstream's commits;
- `scripts/check-image.py <image>`: packages, filesystem, labels and configuration against
  the stock image, and that no template names a patched script without its version;
- `scripts/check-iris.sh <image>`: IRIS against the stock 2.4.29 database: the modules'
  health, the start line, and the worker's log of the exception that a signal handler
  raises in a pool child; CI also runs that last check on `2.4.29-1` as a control
  (`--control`), where the exception must stay out of the log;
- `scripts/check-ui.py <image> --old <image>`: the Overview's columns and the notes editor in
  a browser, against the stock 2.4.29 database and nginx, with the swap from `--old` and the
  way back; CI runs it with `--old` set to `2.4.29-2`, and runs `--control` on `2.4.29-2`,
  where every check of the new behaviour must fail and every other pass. Its tool, Playwright
  for Python, is pinned with hashes in `scripts/check-ui-requirements.txt` and installed with
  the hashes checked into a virtual environment (the script's docstring has the commands); it
  drives Google Chrome, or the Chromium-family browser `--browser` names.

Secret scanning runs as git hooks (`git config core.hooksPath .githooks`, once per clone)
and in CI.

## Releasing

A release is one annotated tag, `v<version>`, and
[`.github/workflows/release.yml`](.github/workflows/release.yml) does the rest. A later fix
of the 2.x line is a release of its own, `2.4.29-N`.

1. `VERSION` holds the new version, the only place it is declared; the build checks its
   base part against IRIS's own version.
2. `CHANGELOG.md` gets the version's entry: placeholders for the date, the digest, the
   image Id and the Python, the base digest, and the notes, which are the tag message to be.
   A version that changes a script under `app/static` again gives it a new `v` in every
   template that names it.
3. `main` is pushed and CI is green on the commit the tag will name. The release runs the
   same checks on the runner before it publishes, and a tag is never pushed again, so a
   failure after the tag would cost the version.
4. The annotated tag names that commit, with the message the `CHANGELOG.md` entry carries.
   The workflow refuses a lightweight tag, or one that differs from `VERSION`, before it
   builds anything.
5. The workflow publishes `ghcr.io/janwychowaniak/iris-web-2x:<version>` (no `latest`),
   then attaches the archive and its checksum to the GitHub Release. Its archive job first
   reads the image without a credential: should the package not be public, it stops there;
   make the package public and re-run the failed job.
6. The date, the digest, the Id and the Python from the run's step summary go into the
   `CHANGELOG.md` entry, in a commit of their own.

## License

LGPL-3.0-or-later, as IRIS. [`LICENSE`](LICENSE) carries the LGPL-3.0 text,
[`COPYING`](COPYING) the GPL-3.0 text it builds on, and [`NOTICE`](NOTICE) the files of
IRIS this image modifies and where each change comes from. The image carries all three in
`/usr/share/doc/iris-web-2x/`.
