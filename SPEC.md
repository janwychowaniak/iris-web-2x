# iris-web-2x — specification of `v2.4.29-2`

This is the implementation specification of `v2.4.29-2`, agreed in rounds between the
owner, the consumer and the maintainer; the rounds themselves are kept outside the
repository. It is temporary: after the release, what lasts moves into `README.md` and
`CHANGELOG.md`, and this file is removed. The specification of `v2.4.29-1` stays readable
as `git show 5a8af53:SPEC.md`.

## 1. The release

`2.4.29-2` is `2.4.29-1` (same stock base, same changes) plus:

- **A.** IRIS's database migration at start no longer disables the loggers that exist at
  that moment, in either target of the entrypoint, `iriswebapp` and `iris-worker` (§3);
- **B.** the renderer's version 0.2.0 names the files it was released with (§4).

Nothing else changes. The labels keep their keys and values but for the version, the
revision and the creation time; `org.opencontainers.image.description` stays as it is.

## 2. Decisions

IDs: `O` the owner's decisions in the order; `Z` the maintainer's assumptions, held unless
vetoed; `W` decisions for the owner; `P` gaps in the order, for the consumer. Round 01 is
the order with `reply-01`.

| ID | Decision | Status | Round |
|---|---|---|---|
| O1–O4 | As in the order's §3: A and B and nothing else; the requirement is the order's §4.1, the mechanism the maintainer's; version `2.4.29-2`, tag `v2.4.29-2`, the README's release procedure; nothing public without the owner's word, implementation only after the owner's go on this file | agreed | 01 |
| Z1 | The change is `disable_existing_loggers=False` in the one call, as patch `0007-alembic-env-keep-loggers.patch` (§3.2) | proposed | 01 |
| Z2 | The CI test raises from a test-only `worker_process_init` handler that a mounted `sitecustomize.py` connects in each pool child; no broker (§3.3) | proposed | 01 |
| Z3 | CI runs the test on `2.4.29-1`, pinned by its registry digest, as a control that must fail for the expected reason; the step is green when it does (§3.3) | proposed | 01 |
| Z4 | The measurement's method (§3.4); its tooling stays out of the repository, its results go into §3.4 | proposed | 01 |
| Z5 | B by the released text: `render.py` returns to its text in `v2.4.29-1`; the version stays 0.2.0 (§4) | proposed | 01 |
| Z6 | The README, the notice, the Dockerfile's comments and `CHANGELOG.md` as in §5; the README's examples name `2.4.29-2` | proposed | 01 |
| Z7 | The tag message lists every change of the image, those of `2.4.29-1` included (§7) | proposed | 01 |
| Z8 | Steps as in §6 | proposed | 01 |
| W1 | The measurement on `2.4.29-1` runs before the go on this file (step 0, §6) | open | 01 |

## 3. Part A — the loggers

### 3.1 The cause

In the sources of IRIS 2.4.29 (`dfir-iris/iris-web` tag `v2.4.29`, under `source/`):

- `app/__init__.py:65` configures the root logger with `basicConfig(level=INFO)`;
  `app/__init__.py:173` imports `app.views`, whose module body calls `run_post_init`
  (`app/views.py:119`).
- With `IRIS_WORKER` unset, `run_post_init` runs the migration,
  `command.upgrade(alembic_cfg, 'head')` (`app/post_init.py:158`); with it set, it skips
  every database step.
- Alembic executes `app/alembic/env.py`, whose line 12 is
  `fileConfig(config.config_file_name)`, with the default `disable_existing_loggers=True`.
  It is the only `fileConfig` or `dictConfig` call in the sources.
- `app/alembic.ini` names `root` (WARN, one stderr `StreamHandler` with the format
  `%(asctime)s :: %(levelname)s :: %(module)s :: %(funcName)s :: %(message)s`),
  `sqlalchemy.engine` (WARN), `app` (INFO) and `alembic` (INFO).
- Python 3.9's `fileConfig` then sets every existing logger that is neither named in the
  file nor a child of a named one to `disabled = disable_existing_loggers`; it resets the
  children of named loggers to level `NOTSET`, no handlers and `propagate = True`.

Both targets import the application once per start: the worker's parent while Celery loads
`app.celery`, before it forks the pool; gunicorn, without `--preload`, in its worker
process. Celery 5.2.7 logs how a task ended through `celery.app.trace` and the exception of
a signal handler through `celery.utils.dispatch.signal`
(`Signal handler %r raised: %r`, with the traceback). The measurement (§3.4) records which
loggers end up disabled in each target.

### 3.2 The change (Z1)

`app/alembic/env.py`, line 12:

```python
fileConfig(config.config_file_name, disable_existing_loggers=False)
```

With it, `fileConfig` sets `disabled = False` where it set `True`, and does everything else
as before: the root logger, the three named loggers and the children of named loggers are
configured as in `2.4.29-1`. What runs after post-init (Celery's own logging set-up in the
worker) runs as before.

- The patch `patches/0007-alembic-env-keep-loggers.patch` changes that line only.
- `patches/stock.sha256` gains
  `58ffa9241e20eca8559dd9fdc0e75a68aed65768ebd3338bb4795b5b1c8172c1  app/alembic/env.py`
  (the stock file, equal to the tag's); `patches/patched.sha256` gains the patched file's
  sha256. The build checks both as for the other patches; the file keeps mode `644` and
  owner `root:root`, which `scripts/check-image.py` checks with the other patched files.
- The README's table of changes gains a row and the notice an entry, both naming the change
  as this repository's own (§5).

### 3.3 The test in CI (Z2, Z3)

A check in `scripts/check-iris.sh`, against the stock database it already starts, with
`IRIS_WORKER` unset as in its other checks:

- The worker runs from the image's entrypoint as `./iris-entrypoint.sh iris-worker`, with a
  test-only directory mounted read-only and named by `PYTHONPATH`. Its `sitecustomize.py`
  registers an at-fork hook; in each pool child it connects a `worker_process_init`
  handler (the signal patch 0002's handler is connected to) that writes a marker line to the
  process's stderr, bypassing `logging`, and then raises `RuntimeError`.
- No broker: Celery starts the pool before the consumer (the `Pool` bootstep comes before
  `Consumer`, which is last), so the children run `worker_process_init` without one.
- On the built image the check passes when the worker's log holds the marker and, from the
  same pool child, `Signal handler <…> raised: RuntimeError(…)` followed by its traceback.
- CI runs the same check on `2.4.29-1`,
  `ghcr.io/janwychowaniak/iris-web-2x@sha256:56c58f51e3ccff58cc9822fc69d91faecf0ace53033fb22c786f0ec2a0044374`,
  as a control: there the marker must appear and the line must not, and the CI step is green
  only then. The marker shows the handler ran, so the control fails for the expected reason.
- The release workflow runs the check on the built image with the other image checks;
  the control runs in CI only.

### 3.4 The measurement (Z4, W1)

For each target, on `2.4.29-1` and on the new image, with `IRIS_WORKER` unset, the stock
2.4.29 database and a RabbitMQ broker:

- **Where:** in the gunicorn worker process once it has loaded the application, through a
  `gunicorn.conf.py` mounted read-only into `/iriswebapp`, which gunicorn 20.1.0 reads from
  its working directory (hook `post_worker_init`); in a pool child of the worker as it runs
  its first task, through a mounted `sitecustomize.py` that connects a `task_prerun` handler
  in each pool child.
- **What:** the root logger and every logger in `logging.root.manager.loggerDict`: name,
  `disabled`, level, effective level, `propagate`, and each handler's class, level, stream,
  and its formatter's format and date format.
- **The task:** the renderer registered and enabled, one IOC update, so one hook task; on the
  new image, the lines that task adds to the worker's log.

The probes write to stderr, outside `logging`; none of them is in the image. Results: to be
filled in, `2.4.29-1` in step 0 or 1, the new image in step 1.

## 4. Part B — the renderer's version (Z5)

`renderer/iris_facade_renderer_module/render.py` returns to its text in `v2.4.29-1`
(`git show v2.4.29-1:renderer/iris_facade_renderer_module/render.py`); it is the only file
of the package that changed since. 0.2.0 then names the files it was released with: the
installed `RECORD` lists each source file with its sha256 and the bytecode without one, so
it, and the package's other metadata files (`INSTALLER`, `METADATA`, `REQUESTED`, `WHEEL`,
`direct_url.json`, `top_level.txt`), equal those of `2.4.29-1` byte for byte. The comment
it brings back refers to §5.4 of the specification of `2.4.29-1`, not of this file. The
tests' docstrings stay as on `main`: the tests are not installed.

## 5. Documentation (Z6)

- **README:** the list of what the image adds gains the loggers' fix; "Six files of IRIS
  change" becomes seven; the table gains the row of `app/alembic/env.py` ("the migration's
  logging configuration leaves the loggers that exist enabled", this repository), and a
  paragraph says what was disabled and why. The examples name `2.4.29-2`.
- **NOTICE:** "six files" becomes seven, and `app/alembic/env.py` is listed as this
  repository's own change: the loggers that exist when the migration configures logging
  stay enabled.
- **Dockerfile:** the header comment names the loggers' fix; the `LABEL` description stays.
- **CHANGELOG.md:** the entry of `2.4.29-2` with placeholders for the date, the digest, the
  image Id and the Python, the base digest, and the notes of §7.
- **VERSION:** `2.4.29-2`.

## 6. Steps (Z8, W1)

Each step ends with a `reply-NN.md`; the consumer verifies it and answers.

0. Before the go (W1): the measurement on `2.4.29-1`, into §3.4.
1. After the go: the patch and its checksums, B, the check of §3.3 with its control,
   `VERSION`, the documentation of §5; a local classic build, the CI scripts run locally on
   it, the control on `2.4.29-1`; the measurement on the new image, into §3.4.
2. On the owner's word, the push; CI green on GitHub on that commit; the tag message shown
   to the owner.
3. The tag on the owner's word, the release, the owner's commit of the published values,
   the consumer's acceptance of the published image and the archive, and the removal of this
   file.

## 7. The tag message, to be (Z7)

```
iris-web-2x 2.4.29-2

DFIR-IRIS 2.4.29 (ghcr.io/dfir-iris/iriswebapp_app@sha256:d7d23026bdde593278075821d3abc8649fe28d618d5784cc9875bd7a3d05699b) with:
- the Celery worker's pool children drop the database session and connections inherited
  from their parent: iris-backend 294ed4a1 and the tasks.py change of 9098c754;
- the loggers that exist when IRIS's database migration configures logging at start stay
  enabled, in the application and in the worker: among them Celery's, which log how each
  task ended and the exception a signal handler raised;
- IrisFacadeRenderer 0.2.0 built in: state by badge classes, ENVELOPE.md v1 only,
  an unrecognised value shown as "?" without stopping the other tabs;
- IrisWebHooks 1.0.9+jw.2 (fork) in place of 1.0.9;
- the attribute tab buttons of IRIS's modals open their panes under its Bootstrap 4.6.2,
  whatever the tab's name;
- the image version in labels, in /usr/share/doc/iris-web-2x/VERSION and in the start log.
```
