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
vetoed; `W` decisions for the owner; `P` gaps in the order, for the consumer; `C` the
consumer's remarks. Round 01 is the order with `reply-01`, round 02 `query-02` with
`reply-02`, round 03 `query-03` with `reply-03`, round 04 `query-04` with `reply-04`, round 05
`query-05` with `reply-05`.

| ID | Decision | Status | Round |
|---|---|---|---|
| O1–O4 | As in the order's §3: A and B and nothing else; the requirement is the order's §4.1, the mechanism the maintainer's; version `2.4.29-2`, tag `v2.4.29-2`, the README's release procedure; nothing public without the owner's word, implementation only after the owner's go on this file | agreed | 01 |
| Z1 | The change is `disable_existing_loggers=False` in the one call, as patch `0007-alembic-env-keep-loggers.patch` (§3.2) | agreed | 02 |
| Z2 | The CI test raises from a test-only `worker_process_init` handler that a mounted `sitecustomize.py` connects in each pool child; no broker (§3.3) | agreed | 02 |
| Z3 | CI runs the test on `2.4.29-1`, pinned by its registry digest, as a control that must fail for the expected reason; the step is green when it does (§3.3) | agreed | 02 |
| Z4 | The measurement's method (§3.4); its tooling stays out of the repository, its results go into §3.4 | agreed | 02 |
| Z5 | B by the released text: `render.py` returns to its text in `v2.4.29-1`; the version stays 0.2.0 (§4) | agreed | 02 |
| Z6 | The README, the notice, the Dockerfile's comments and `CHANGELOG.md` as in §5; the README's examples name `2.4.29-2` | agreed | 02 |
| Z7 | The tag message lists every change of the image, those of `2.4.29-1` included (§7) | agreed | 02 |
| Z8 | Steps as in §6 | agreed | 02 |
| W1 | The measurement on `2.4.29-1` runs before the go on this file (step 0, §6) | agreed (owner) | 02 |
| C1 | The check reads the log only after a second receiver, connected after the raising one, has written its own marker, so the control's absence is read past the point where the line would come (§3.3) | agreed | 02 |
| C2 | The measurement's probes, with how the stack and the task are started, are handed over in the rounds folder with the reply of the step that first uses them (§3.4) | agreed | 02 |
| O4 | The owner's go on this file for the implementation | given (owner) | 03 |
| C3 | `scripts/check-iris.sh` and the measurement's `run.sh` remove their containers with their anonymous volumes (`docker rm -v`) | agreed | 03 |
| C4 | The README's list of checks names `2.4.29-1` as the control's image | agreed | 04 |
| C5 | The README says where the updater's ERROR at the worker's start comes from (§3.4, §5) | agreed | 04 |
| C6 | The control's `FAIL` line says how many lines of the exception the log holds | agreed | 04 |
| O5 | The consumer's K7, K11 and K12 run once, on the published image, with K8–K10; its acceptance of the local build is K2–K6 and K13 | given (owner) | 05 |

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

A check in `scripts/check-iris.sh`, the signal log, against the stock database it already
starts, with `IRIS_WORKER` unset as in its other checks; the probe is
`scripts/signal-probe/sitecustomize.py`:

- The worker runs from the image's entrypoint as `./iris-entrypoint.sh iris-worker`, with a
  test-only directory mounted read-only and named by `PYTHONPATH`. Its `sitecustomize.py`
  registers an at-fork hook; in each pool child it connects two `worker_process_init`
  handlers (the signal patch 0002's handler is connected to), after patch 0002's: the first
  writes a marker line to the process's stderr, bypassing `logging`, and raises
  `RuntimeError`; the second writes a second marker the same way (C1). Celery's
  `Signal.send` calls the receivers in the order they were connected and logs a receiver's
  exception before it calls the next, so Celery's line, if it comes, comes between the two
  markers. The check reads the worker's stderr, one stream in the order the processes
  wrote it, once a pool child's second marker is in it.
- No broker: Celery starts the pool before the consumer (the `Pool` bootstep comes before
  `Consumer`, which is last), so the children run `worker_process_init` without one.
- On the built image the check passes when, for every pool child that wrote both markers,
  and at least one did, the worker's log holds between them
  `Signal handler <…> raised: RuntimeError('iw2x-signal-probe <process name>')` followed by
  its traceback.
- CI runs the same check on `2.4.29-1`,
  `ghcr.io/janwychowaniak/iris-web-2x@sha256:56c58f51e3ccff58cc9822fc69d91faecf0ace53033fb22c786f0ec2a0044374`,
  as a control, through `scripts/check-iris.sh --control <image>`, which starts the database
  and runs this check alone. There at least one pool child must write both markers and the
  log must hold no line of the exception, and the CI step is green only then. The markers show that the handler ran and that the point
  where the line would come has passed, so the control fails for the expected reason.
- The release workflow runs the check on the built image with the other image checks;
  the control runs in CI only.

### 3.4 The measurement (Z4, W1)

For each target, on `2.4.29-1` and on the new image, with `IRIS_WORKER` unset, on a fresh
stock 2.4.29 database with the upstream compose's broker, `rabbitmq:3-management-alpine`,
both pinned by digest; the app started as the upstream compose starts it, then the worker
through `wait-for-iriswebapp.sh`:

- **Where:** in the gunicorn worker process once it has loaded the application, through a
  `gunicorn.conf.py` mounted read-only into `/iriswebapp`, which gunicorn 20.1.0 reads from
  its working directory (hook `post_worker_init`); in a pool child of the worker as it runs
  its first task, through a mounted `sitecustomize.py` that connects a `task_prerun` handler
  in each pool child, importing nothing new.
- **What:** the root logger and every logger in `logging.root.manager.loggerDict`: name,
  `disabled`, level, effective level, `propagate`, and each handler's class, level, stream,
  filters and formatter (class, format, date format). IRIS names one logger per module
  instance `iris_interface.IrisModuleInterface_<8 random letters>`; the comparison takes
  them as one name.
- **The task:** the renderer registered and enabled, one IOC added and then updated, so one
  hook task (IRIS's default modules are registered disabled); the lines the update adds to
  the worker's log.

The probes write the state to a file inside the container and one line to stderr, outside
`logging`; none of them is in the image. They are handed over in the rounds folder with
the reply of step 0, with the script that starts the stack and the task (C2).

**Results on `2.4.29-1`** (step 0). Two runs, each on a fresh database, gave the same
disabled sets, the same digests and the same task lines.

| | gunicorn worker (`iriswebapp`) | pool child at its first task (`iris-worker`) |
|---|---|---|
| Loggers, the root included | 203 | 218 |
| Disabled | 179 | 173 |
| Root | WARNING; one stderr `StreamHandler`, the format of `alembic.ini` | INFO; Celery's stderr `StreamHandler`, `[%(asctime)s: %(levelname)s/%(processName)s] %(message)s` |
| sha256 of every property but `disabled` | `622b65f047ffda3ee8fd24abbab2ae59bbaac7f9af5b5f8229e7de82e96153ea` | `1da2e81992f0b533aefaf119560ebac7b5ac0a208002d14bfd0dc08e8c1c2614` |

Enabled in both: the root, `app`, `alembic` and `sqlalchemy.engine` with their children,
and the loggers created after post-init (in the worker, for example `celery.apps.worker`,
`celery.beat` and `celery.worker.consumer.*`). Disabled, among those that would write:

- in the gunicorn worker: `gunicorn.error` (INFO, its own stderr handler,
  `%(asctime)s [%(process)d] [%(levelname)s] %(message)s`, propagation off) and
  `gunicorn.access` (INFO, no handler: gunicorn runs without an access log), with
  `gunicorn`, `gunicorn.http` and `gunicorn.http.wsgi`; `engineio.server` and
  `socketio.server` (ERROR, their own stderr handlers); and, at the root's WARNING,
  `sqlalchemy` and its children outside `sqlalchemy.engine`, `celery`, `kombu.common`,
  `kombu.connection`, `amqp`, `urllib3` and `requests`;
- in the pool child: `celery.app.trace`, `celery.utils.dispatch.signal`,
  `celery.worker.request`, `celery.worker.control`, `celery.pool`, `celery.bootsteps`,
  `celery.task` (INFO, Celery's task handler, propagation off), `kombu.connection`,
  `kombu.common` and three more of kombu's, and `amqp`; and the same library loggers at the
  root's INFO;
- in both: `pyasn1` (DEBUG, its own stderr handler, which pyasn1 0.6.3 sets up when it is
  imported). It writes only once pyasn1's debug flags are set, and no other package in the
  image sets them.

The lines that the one hook task adds to the worker's log, the probe's own line left out:

```
[…: INFO/MainProcess] Task app.iris_engine.module_handler.module_handler.task_hook_wrapper[<id>] received
[…: INFO/ForkPoolWorker-5] Calling module iris_facade_renderer_module for hook on_postload_ioc_update
[…: INFO/ForkPoolWorker-5] Retrieved server configuration
[…: INFO/ForkPoolWorker-5] Module has initiated
[…: INFO/ForkPoolWorker-5] Received on_postload_ioc_update
[…: INFO/ForkPoolWorker-5] IOC #1: rendered tab 'VT Report'
```

Nothing from `celery.app.trace`, while the task's state in the result backend is `SUCCESS`.

**Results on the new image** (step 1, the build of `c1db458`): no logger disabled in either
target, of the same 203 and 218, and the same two sha256s as on `2.4.29-1`; only `disabled`
differs. The hook task adds the lines above and, after them, `celery.app.trace`'s:

```
[…: INFO/ForkPoolWorker-5] Task app.iris_engine.module_handler.module_handler.task_hook_wrapper[<id>] succeeded in 0.165917765814811s: <iris_interface.IrisInterfaceStatus.IIStatus object at 0x…>
```

`IIStatus` defines no `__repr__`, so the line carries no data of the module. Beyond the task,
the app's log is the same as on `2.4.29-1`, and the worker's log gains one record at every
start, after post-init:

```
… :: ERROR :: signal :: send :: Signal handler <function setup_periodic_update_checks at 0x…> raised: TypeError("setup_periodic_update_checks() missing 1 required positional argument: 'self'")
Traceback (most recent call last):
  File "/opt/venv/lib/python3.9/site-packages/celery/utils/dispatch/signal.py", line 276, in send
    response = receiver(signal=self, sender=sender, **named)
TypeError: setup_periodic_update_checks() missing 1 required positional argument: 'self'
```

That is a fault of IRIS 2.4.29 that the disabled logger hid, not one the change causes:
`app/iris_engine/updater/updater.py:587` connects `setup_periodic_update_checks(self, **kwargs)`
to `celery.on_after_finalize`, which calls its receivers with `sender=` as a keyword, so the
daily update check `iris_auto_check_updates` is never scheduled at start. It is out of scope
(the order's §6); the order's K7 counts such a line as a finding for a release of its own.

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
  paragraph says what was disabled and why, and another the updater's ERROR that the worker's
  log shows at every start (C5). The list of checks names the signal log and its control on
  `2.4.29-1` (C4). The examples name `2.4.29-2`.
- **NOTICE:** "six files" becomes seven, and `app/alembic/env.py` is listed as this
  repository's own change: the loggers that exist when the migration configures logging
  stay enabled.
- **Dockerfile:** the header comment names the loggers' fix; the `LABEL` description stays.
- **CHANGELOG.md:** the entry of `2.4.29-2` with placeholders for the date, the digest, the
  image Id and the Python, the base digest, and the notes of §7.
- **VERSION:** `2.4.29-2`.

## 6. Steps (Z8, W1)

Each step ends with a `reply-NN.md`; the consumer verifies it and answers.

0. Before the go (W1): the measurement on `2.4.29-1`, into §3.4; its probes to the rounds
   folder (C2).
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
