# iris-web-2x — specification of the first release, `v2.4.29-1`

This is the implementation specification of `v2.4.29-1`, agreed in rounds between the
owner, the consumer and the maintainer; the rounds themselves are kept outside the
repository. It is temporary: after the release, what lasts moves into `README.md` and
`CHANGELOG.md`, and this file is removed. Out of scope: the order's §9.

## 1. The image

`ghcr.io/janwychowaniak/iris-web-2x:2.4.29-N` is the stock DFIR-IRIS application image
`ghcr.io/dfir-iris/iriswebapp_app:v2.4.29` plus:

- **A.** two upstream fixes for the Celery worker (§4);
- **B.** the IrisFacadeRenderer module 0.2.0, built from this repository (§5);
- **C.** the IrisWebHooks fork `1.0.9+jw.2` in place of the stock 1.0.9 (§6);
- **D.** its own version, in a version file, in labels and in the start log (§7).

Nothing else changes. It runs the web application and the worker exactly as the stock
image does, from the same compose file; nginx and the database stay stock 2.4.29.
Platform: linux/amd64.

## 2. Decisions

IDs: `O` the owner's decisions in the order; `Z` the maintainer's assumptions,
held unless vetoed; `W` decisions for the owner. Round 01 is the order with `reply-01`.

| ID | Decision | Status | Round |
|---|---|---|---|
| O1–O10 | As in the order's §3: public repository and image name; thin layer over the stock image; upstream's patch text byte for byte; layered releases; LGPL-3.0-or-later; versions `v2.4.29-N` / `2.4.29-N`; the fork at tag `v1.0.9+jw.2`; no module registration by the image; the sibling's release shape; nothing public without the owner's word | agreed | 01 |
| Z1 | Version file `VERSION`, copied into the image (§7.1) | open | 01 |
| Z2 | The start line's text and position (§7.3) | open | 01 |
| Z3 | Inherited base labels are overridden, `created` is the commit time (§7.2) | open | 01 |
| Z4 | License files `LICENSE`, `COPYING`, `NOTICE`; in the image under `/usr/share/doc/iris-web-2x/` (§8) | open | 01 |
| Z5 | What counts as an ENVELOPE.md v1 shape (§5.4) | open | 01 |
| Z6 | Rendering details the order leaves open (§5.5) | open | 01 |
| Z7 | A failed tab write: rollback, the call reports failure (§5.6) | open | 01 |
| Z8 | CI also compares packages and filesystem with the base (K2, K3) and runs the archive round trip on every push (§9) | open | 01 |
| Z9 | CI and release run on `ubuntu-24.04`, not `ubuntu-latest` (§9, §10) | open | 01 |
| Z10 | The release runs the image checks before the push (§10) | open | 01 |
| Z11 | Implementation in four steps (§12) | open | 01 |
| W1 | The package `ghcr.io/janwychowaniak/iris-web-2x` is public and linked to this repository, as vt-proxy's is | agreed (owner) | 01 |

## 3. The base and the build

- `FROM ghcr.io/dfir-iris/iriswebapp_app@sha256:d7d23026bdde593278075821d3abc8649fe28d618d5784cc9875bd7a3d05699b`,
  the OCI index of tag `v2.4.29`. Its linux/amd64 manifest is
  `sha256:5b03716bea7889b5fd8e7374f7b521bc509f1dc75c1e67b8f48c4dd4406a664c`, configuration
  `sha256:f6af6018f65f3f01f6ce84dce2b89b5c4bcff663ba9c585450b9d0016531c6b5`, 558 MB of
  compressed layers.
- The base as built from `dfir-iris/iris-web` at `340ce040`: IRIS sources in `/iriswebapp`
  (`WORKDIR`), Python 3.9.25 in `/opt/venv`, pip 23.0.1, setuptools 70.3.0, no `ENTRYPOINT`
  (compose passes the command). `patch`, `git` and `sha256sum` are present.
- The Dockerfile builds with the classic builder (`DOCKER_BUILDKIT=0`): no BuildKit syntax.
- Network during the build: ghcr.io (the base) and github.com (the fork) only. Both
  packages are installed with `pip install --no-deps --no-index --no-cache-dir` from a local
  directory. Neither has a `pyproject.toml`, so pip 23 builds them without an isolated build
  environment and fetches nothing; the renderer keeps `setup.py` only for this reason.
- Nothing is left behind: build files live in a temporary directory removed in the same
  step, pip keeps no cache, and no IRIS code runs during the build.

Repository layout:

```
Dockerfile, .dockerignore, VERSION
patches/   0001-module-handler-reset-session.patch, 0002-tasks-worker-process-init.patch,
           0003-entrypoint-version-line.patch, stock.sha256, patched.sha256
renderer/  setup.py, iris_facade_renderer_module/, tests/
scripts/   the CI and release checks
.github/   workflows/{ci,release,gitleaks}.yml, scripts/archive-image.sh
LICENSE, COPYING, NOTICE, README.md, CHANGELOG.md
```

## 4. Part A — the worker fixes

### 4.1 The patches

| File | Upstream | Change |
|---|---|---|
| `patches/0001-…` | `dfir-iris/iris-backend` `294ed4a19bf7cfe60c75f20cacdbc79d91ce6a9f`, its only change | in `app/iris_engine/module_handler/module_handler.py`, at the entry of `task_hook_wrapper`: upstream's comment, `db.session.remove()`, `db.engine.dispose()` |
| `patches/0002-…` | `dfir-iris/iris-backend` `9098c754089d28e9ebe448fb37a9ae55403b8b7e`, its `source/app/iris_engine/tasker/tasks.py` change only | in `app/iris_engine/tasker/tasks.py`: the import of `task_prerun` becomes `worker_process_init`; the `task_prerun` handler becomes a `worker_process_init` handler calling `db.engine.dispose(close=False)` inside `app.app_context()`, with upstream's docstring and comment |
| `patches/0003-…` | this repository's own change | §7.3 |

Each patch is written against the 2.4.29 file, so it applies without offset or fuzz. The
lines it adds and removes are upstream's byte for byte (O3); the context lines are
2.4.29's. In 2.4.29, `tasks.py` already imports `app` at module scope and `db` from `app`;
the handler's deferred `from app import app` stays as upstream wrote it.

The docstring of the second patch describes the 3.x layout and stays verbatim: it refers to
a gunicorn `post_fork` hook, which 2.4.29 does not have (its gunicorn runs without a
configuration file), and to `pool_pre_ping` in `app/db.py`, which 2.4.29 sets in
`app/__init__.py`. 2.4.29 runs SQLAlchemy 2.0.24, which supports `dispose(close=False)`.

### 4.2 Application and checks

During the build, from `/iriswebapp`:

1. `sha256sum -c patches/stock.sha256`, the stock values:

   | File | sha256 |
   |---|---|
   | `app/iris_engine/module_handler/module_handler.py` | `fc00eed2de2a8177361f5a9d5815988aaaa57124cfb97962afe88edfa95cb673` |
   | `app/iris_engine/tasker/tasks.py` | `32b2ca7288580ccd731c761b73d97262ab1f1a0111a8180d939fb373b44c2ee3` |
   | `iris-entrypoint.sh` | `d85ad9552eb8f96bd32dcf8d9370e1f8b1fc8b7752e560ae38ef68dd22ae93a4` |

2. `patch -p1 --forward --fuzz=0 --no-backup-if-mismatch` for each patch, so no `*.orig`
   or `*.rej` can appear;
3. `sha256sum -c patches/patched.sha256`, the patched values the repository records;
4. `iris-entrypoint.sh` is still mode `755`, owner `root:root`.

Any mismatch fails the build. CI proves O3: it fetches the two upstream commits from
github.com and checks that the added and the removed lines of each patch equal those of
its upstream file change.

## 5. Part B — IrisFacadeRenderer 0.2.0

### 5.1 What stays

Import name `iris_facade_renderer_module`, module name `IrisFacadeRenderer`, interface
version 1.2.0, type processor; parameters `frr_on_update_hook_enabled` and
`frr_manual_hook_enabled`, both defaulting to true; hooks `on_postload_ioc_update` and
`on_manual_trigger_ioc` with the manual hook name `Render facade reports`; tabs `VT Report`,
`AbuseIPDB Report`, `URLScan Report`, `<key> Report` for any other key; the field
`HTML report` of type `html`; one tab per service key, rendered from that key's value
alone. 0.2.0 replaces 0.1.1 in place: a database that registered 0.1.1 keeps its
registration, configuration and hooks, and Manage → Modules keeps showing `0.1.1`, the
version stored at registration.

### 5.2 Structure

- `render.py` holds the shape check, the HTML and the loop over IOCs and keys. It imports
  only the standard library, so the tests reach it without IRIS (§11).
- `IrisFacadeRendererInterface.py` is the IRIS side: hook registration as in 0.1.1, and the
  tab writer, `add_tab_attribute_field` with a rollback on failure (§5.6).
- `setup.py` only, version `0.2.0`.

### 5.3 Data

The data is the IOC field `ioc_enrichment` (JSONB), an object keyed by service (`vt`,
`abuseipdb`, `urlscan`), each value one answer of a facade under ENVELOPE.md v1 (vt-proxy
`v0.4.0`, `b43a998`; identical in abuseipdb-proxy).

### 5.4 The v1 shapes (Z5)

- **Response envelope:** an object with exactly the keys `query`, `known`, `verdict`,
  `report`; `query` an object whose `artifact` is a string; `known` a boolean; with
  `known: true`, `verdict` an object whose `score` is a number; with `known: false`,
  either `verdict` and `report` both null, or `verdict` an object whose `score` is a number
  (a record).
- **Error body:** an object with exactly the key `error`, whose value is an object with a
  string `code` and a string `message` and no keys besides `code`, `message`, `upstream`.
- A number is a JSON integer or float; a boolean is not a number.
- Fields the renderer does not read are not checked: `query.type`, `query.msg`, a facade's
  parameters, `verdict.thresh_gte` and a facade's own verdict fields, `error.upstream`.
- Anything else is unrecognised.

### 5.5 Output

No `style` attribute anywhere; state is a Bootstrap 4.6 badge, recoloured by IRIS's
`atlantis.css` (`body .badge-danger` `#9D2F35`, `body .badge-success` `#056F08DB`,
`body .badge-warning` `#DF7D03A3`, `.badge-light` `#d7d7d7`).

| Value under a service key | Badge | Besides the badge |
|---|---|---|
| envelope, `known: true`, score above 0 | `<span class="badge badge-danger">score N/T</span>` | the artifact, the detail rows, the analysis stats, the names |
| envelope, `known: true`, score 0 or below | `<span class="badge badge-success">score N/T</span>` | as above |
| envelope, `known: false`, `verdict` and `report` null | `<span class="badge badge-light">unknown (no record)</span>` | `No record upstream for <code>ARTIFACT</code>.` |
| envelope, `known: false`, with a record | `<span class="badge badge-light">no findings (score N)</span>` | the artifact and the detail rows |
| error body | `<span class="badge badge-warning">lookup failed (CODE)</span>` | the error's `message` |
| unrecognised | `<span class="badge badge-light">?</span>` | `This value is not an ENVELOPE.md v1 response or error.` |

Rendering details (Z6):

- `N` is the score as Python prints it (`3`, `4.5`). `T` is the sum of the integer values
  of the analysis stats: `verdict.stats` when it is an object, else the record's
  `last_analysis_stats`, as in 0.1.1. When there are none, or they sum to 0, the text is
  `score N`.
- The record is `report.attributes` when that is an object (VirusTotal), else `report`
  when that is an object (AbuseIPDB). Detail rows, a label and a value each, in this order;
  a key missing, null or of another type is left out:

  | Service | Rows (label: key, type) |
  |---|---|
  | `vt` | Country: `country`, string · AS owner: `as_owner`, string · Network: `network`, string · Reputation: `reputation`, integer · Type: `type_description`, string · Meaningful name: `meaningful_name`, string |
  | `abuseipdb` | ISP: `isp`, string · Country: `countryCode`, string · Usage type: `usageType`, string · Domain: `domain`, string · Total reports: `totalReports`, integer · Last reported: `lastReportedAt`, string |
  | any other | none |

  An integer is never a boolean.
- Analysis stats: a table of the integer entries, sorted by key. Names: the record's
  `names`, when a list, its string items, the first five, comma-separated.
- Layout: a heading `<h3>` with the service title (`VirusTotal`, `AbuseIPDB`, `URLScan`, or
  the key) and the badge; `<p>artifact: <code>…</code></p>`; detail and stats tables as
  `<table class="table table-sm"><tbody>` rows of `<th>` and `<td>`; a closing
  `<p class="small text-muted">via KEY facade &middot; rendered by IrisFacadeRenderer 0.2.0</p>`.
  Every tag and attribute is in the 2.4.29 filter's allow list, so the filter leaves the
  output unchanged.
- Every value taken from the data is HTML-escaped (`html.escape`, quotes included), the key
  in the heading and the closing line included. The tab name is written as `KEY Report`
  without escaping, because IRIS's templates autoescape it.

### 5.6 The hook call (Z7)

- An IOC without `ioc_enrichment`, or with one that is not an object or is empty: log
  `IOC #ID: no ioc_enrichment, nothing to render`, nothing written.
- Otherwise each key is rendered and written with
  `add_tab_attribute_field(ioc, tab_name, field_name="HTML report", field_type="html", field_value=html)`;
  log `IOC #ID: rendered tab 'TAB'`.
- An unrecognised value is rendered with the `?` badge and logged once, at warning:
  `IOC #ID: 'KEY': not an ENVELOPE.md v1 value, rendered as "?"`.
- A write that returns false or raises is a failed tab: the session is rolled back, the
  log says `IOC #ID: tab 'TAB' not written: REASON`, and the other keys and IOCs are still
  written.
- The call reports success when every tab was written, `?` tabs included, and failure
  otherwise. An unsupported hook name is a failure, as in 0.1.1.

## 6. Part C — the IrisWebHooks fork

- The build clones `https://github.com/janwychowaniak/iris-webhooks-module` at tag
  `v1.0.9+jw.2` and fails unless the tag is annotated and resolves to
  `8b30028ee6ec580b2404cccacb49db300eec197e`. The fork has no dependencies.
- It replaces the stock `iris_webhooks_module` 1.0.9 in `/opt/venv`; the package metadata
  reports `1.0.9+jw.2`. The stock wheel stays at
  `/iriswebapp/dependencies/iris_webhooks_module-1.0.9-py3-none-any.whl`.
- On a fresh database IRIS registers `iris_webhooks_module` itself, disabled, as one of its
  default modules, and stores `1.0.9+jw.2`; a database that registered 1.0.9 keeps
  showing 1.0.9.

## 7. Part D — the image's own version

### 7.1 The version file (Z1)

`VERSION` at the repository root holds the image version, `2.4.29-1`, and is the only
place it is declared. The build copies it to `/usr/share/doc/iris-web-2x/VERSION`, takes the
same value as a build argument for the labels, and fails unless the two are equal and the
part before the last `-` equals `IRIS_VERSION` in `/iriswebapp/app/configuration.py`
(`v2.4.29`) without its `v`. The release gate compares the tag with `v` + `VERSION`.

### 7.2 Labels (Z3)

| Label | Value |
|---|---|
| `org.opencontainers.image.version` | `2.4.29-1` |
| `org.opencontainers.image.source` | `https://github.com/janwychowaniak/iris-web-2x` |
| `org.opencontainers.image.revision` | the built commit |
| `org.opencontainers.image.licenses` | `LGPL-3.0-or-later` |
| `org.opencontainers.image.base.name` | `ghcr.io/dfir-iris/iriswebapp_app:v2.4.29` |
| `org.opencontainers.image.base.digest` | the `FROM` digest, `sha256:d7d23026…05699b` |
| `org.opencontainers.image.title` | `iris-web-2x` |
| `org.opencontainers.image.url` | `https://github.com/janwychowaniak/iris-web-2x` |
| `org.opencontainers.image.description` | `DFIR-IRIS 2.4.29 with two upstream worker fixes and two modules built in` |
| `org.opencontainers.image.created` | the built commit's committer time, ISO 8601 |

The base carries its own `title`, `url`, `description` and `created`, which would otherwise
pass through with the stock image's values.

### 7.3 The start line (Z2)

`patches/0003` adds, right after `target=…` and before `Running <target> ...`, the lines
that print, for every target:

```
iris-web-2x 2.4.29-1 (DFIR-IRIS v2.4.29)
```

Both values come from `/usr/share/doc/iris-web-2x/VERSION` (the base version is the part
before the last `-`), so the patch stays the same across `2.4.29-N`. The entrypoint is
otherwise unchanged, including upstream's default `target=${1-:app}`: compose always passes
`iriswebapp` or `iris-worker`.

Switching a deployment from the stock image sets `APP_IMAGE_NAME=ghcr.io/janwychowaniak/iris-web-2x`
and adds `APP_IMAGE_TAG=2.4.29-1`, which the upstream compose shares between the app and the
worker; removing both lines switches back.

## 8. License (Z4)

- `LICENSE`: the LGPL-3.0 text, as the repository was created (byte-identical to Debian's
  `/usr/share/common-licenses/LGPL-3`).
- `COPYING`: the GPL-3.0 text the LGPL builds on, byte-identical to the base image's
  `/usr/share/common-licenses/GPL-3` (sha256 `3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986`).
- `NOTICE`: the modified IRIS files, each with its origin: `app/iris_engine/module_handler/module_handler.py`
  (iris-backend `294ed4a1`), `app/iris_engine/tasker/tasks.py` (iris-backend `9098c754`),
  `iris-entrypoint.sh` (this repository's own change).
- In the image: `/usr/share/doc/iris-web-2x/` holds `LICENSE`, `COPYING`, `NOTICE` and
  `VERSION`; the README names the path.

## 9. CI — `.github/workflows/ci.yml`

On every push and pull request, `runs-on: ubuntu-24.04` (Z9), with a job timeout.

| Check | What |
|---|---|
| tests | the renderer's tests (§11) in the stock base image pinned by digest, without network |
| upstream lines | O3, as in §4.2 |
| build | `DOCKER_BUILDKIT=0 docker build`, which runs the checks of §4.2, §6 and §7.1 |
| packages | `iris_webhooks_module` `1.0.9+jw.2` and `iris_facade_renderer_module` `0.2.0`; `pip freeze --all` differs from the base's in exactly these two lines; the Debian package lists are identical (Z8) |
| filesystem | against the base: the only differences are the two packages in `/opt/venv`, the three patched files and `/usr/share/doc/iris-web-2x/` (Z8) |
| labels | §7.2 |
| filter copy | the 2.4.29 filter configuration the tests use equals the block in the image's `/iriswebapp/app/__init__.py` |
| module health | with the stock `iriswebapp_db:v2.4.29` image pinned by digest: a container of the built image imports IRIS (post-init against that database), then `instantiate_module_from_name` and `check_module_health` pass for both modules |
| start line | the entrypoint run as `iriswebapp` and as `iris-worker` against that database prints §7.3 before gunicorn's or Celery's first line |
| archive | `.github/scripts/archive-image.sh` round trip, without a record (Z8) |

The database and IRIS secrets are generated in the job and masked, never written in the
workflow. `.github/workflows/gitleaks.yml` scans content and commit messages separately.

## 10. Release — `.github/workflows/release.yml`

On every `v*` tag, in the shape of vt-proxy `v0.4.0`, `runs-on: ubuntu-24.04` (Z9):

- **publish** (`contents: read`, `packages: write`): the tag must be annotated and equal
  `v` + `VERSION`, before anything is built; the tests on the tagged commit; the classic
  build of that commit; the image checks of §9, packages to start line (Z10); push of
  `ghcr.io/janwychowaniak/iris-web-2x:<version>` only, no `latest`. The step summary records
  the registry digest, the image Id read from the pushed manifest's configuration digest,
  the Python version and the base digest.
- **archive** (`contents: write`, the only job that writes): pulls the published image by
  digest, tags it `ghcr.io/janwychowaniak/iris-web-2x:<version>`, runs `archive-image.sh`
  against the recorded Id, producing `iris-web-2x-<version>.tar.gz` and `.sha256`, proves
  the archive loads as the same Id into a store without the image, creates or updates the
  GitHub Release from the annotated tag's message with both files, and checks that the
  release notes equal the tag message. A re-run reaches the same end state; a second tag
  is never the fix.

`CHANGELOG.md` has the sibling's header (the notes are the tag messages; a tag is never
pushed again; the Id is what a host compares after `docker load`) and, per version, the
registry digest, the image Id, the Python version, the base digest and the notes. Before
the tag the entry holds placeholders; the owner commits the published values by hand.

The tag message of `v2.4.29-1`, to be:

```
iris-web-2x 2.4.29-1

DFIR-IRIS 2.4.29 (ghcr.io/dfir-iris/iriswebapp_app@sha256:d7d23026…05699b) with:
- the Celery worker's pool children drop the database session and connections inherited
  from their parent: iris-backend 294ed4a1 and the tasks.py change of 9098c754;
- IrisFacadeRenderer 0.2.0 built in: state by badge classes, ENVELOPE.md v1 only,
  an unrecognised value shown as "?" without stopping the other tabs;
- IrisWebHooks 1.0.9+jw.2 (fork) in place of 1.0.9;
- the image version in labels, in /usr/share/doc/iris-web-2x/VERSION and in the start log.
```

## 11. Tests

The renderer's tests use the standard library's `unittest` and run in the stock base image
(Python 3.9.25, bleach 6.1.0 as in IRIS), importing `render.py` only: importing IRIS's `app`,
or `iris_interface`, which imports `app`, starts IRIS and its post-init exits without a
database.

1. Every row of §5.5 to its badge class, text and details, including `score N/T`,
   `score N` without stats, and a negative score.
2. To the `?` tab, with one log line and no exception: `known: true` with a string, a
   boolean or a null score; `query` as a string; a string; a list; an object with other
   keys; an envelope missing a key; an error body with an extra key.
3. In one call, a bad value does not stop the other keys of its IOC or the other IOCs; the
   call reports success.
4. A failing tab write: logged, the rest written, the call reports failure.
5. Details of the wrong type left out without an exception: a list as `report`, a
   non-string among the names, a detail of the wrong type, non-integer stats.
6. Hostile strings (`<img src=x onerror=alert(1)>`, quotes, `&`) escaped in every field,
   the key and the error's code and message included.
7. The output of every row passed through the 2.4.29 filter configuration (bleach 6.1.0,
   `strip=True`) comes out unchanged: every class intact, no `style` anywhere.
8. §5.1's names, parameters, defaults and hook name, pinned.

## 12. Steps (Z11)

Each step ends with a `reply-NN.md`; the consumer verifies it and answers.

1. Dockerfile, `VERSION`, the three patches and their checks, the fork, labels, license
   files: a classic build that passes §4.2, §6, §7 and §8.
2. Renderer 0.2.0 and its tests.
3. `ci.yml` with every check of §9, green on GitHub.
4. `release.yml`, `archive-image.sh`, `CHANGELOG.md`, `README.md`; then the tag text to the
   owner.
