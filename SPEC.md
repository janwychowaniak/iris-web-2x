# iris-web-2x — specification of `v2.4.29-3`

This is the implementation specification of `v2.4.29-3`, agreed in rounds between the
owner, the consumer and the maintainer; the rounds themselves are kept outside the
repository. It is temporary: after the release, what lasts moves into `README.md` and
`CHANGELOG.md`, and this file is removed. The specifications of the earlier releases stay
readable as `git show 5a8af53:SPEC.md` (`v2.4.29-1`) and `git show 260485d:SPEC.md`
(`v2.4.29-2`).

## 1. The release

`2.4.29-3` is `2.4.29-2` (same stock base, same changes) plus:

- **A.** on the Overview, each user shows or hides the table's columns, Title excepted, and
  the choice is remembered (§4);
- **B.** the choice to show or hide a note's editor is one choice for all notes, and it is
  remembered (§5);
- **C.** the deployment sets the defaults of A and B with two environment variables of the
  app; with neither set, the defaults are those of 2.4.29 (§6).

A browser that has used `2.4.29-2` or the stock 2.4.29 gets A, B and C after the swap, and
the previous behaviour after a way back (§7). Nothing else changes. The labels keep their
keys and values but for the version, the revision and the creation time;
`org.opencontainers.image.description` stays as it is.

## 2. Decisions

IDs: `O` the owner's decisions in the order; `Z` the maintainer's assumptions, held unless
vetoed; `W` decisions for the owner; `P` gaps in the order, for the consumer. Round 01 is
the order with `reply-01`.

| ID | Decision | Status | Round |
|---|---|---|---|
| O1–O5 | As in the order's §3: A, B and C and nothing else; the order's §4–§7 are the requirements, the mechanism the maintainer's; with no variable set, a user who has made no choice sees what 2.4.29 shows; version `2.4.29-3`, tag `v2.4.29-3`, the README's release procedure; nothing public without the owner's word, implementation only after the owner's go on this file | agreed | 01 |
| Z1 | The choices are kept per browser, in the `localStorage` of the IRIS site, as IRIS keeps its own (§4.2) | proposed | 01 |
| Z2 | The Overview's control is IRIS's column visibility button of its case tables, with a last entry, `Default columns`; Export, Copy and row selection stay absent (§4.1) | proposed | 01 |
| Z3 | Each column gets its filter field from IRIS's own `tableFiltering` while every column is visible, before the defaults or the choice apply; hiding a column clears its field and its search; `datatablesUtils.js` stays stock (§4.3) | proposed | 01 |
| Z4 | The round button's toggle is the editor's choice; an opened note takes it, a created note opens with its editor; hiding the editor ends its expansion (§5) | proposed | 01 |
| Z5 | The variables `IW2X_OVERVIEW_COLUMNS` and `IW2X_NOTE_EDITOR`, read from the environment in `app/configuration.py`; their values, an unusable value and the start log's lines as in §6, the lines in the app's log only | proposed | 01 |
| Z6 | The patched templates name the patched scripts with `?v=2.4.29-3`; a check proves that no template in the image names either script without a `v` (§7, §9.1) | proposed | 01 |
| Z7 | Five files of IRIS are patched, none is added (§8) | proposed | 01 |
| Z8 | The browser test of §9.2, in CI and in the release, with its control on `2.4.29-2` in CI | proposed | 01 |
| Z9 | The README, the notice, the Dockerfile's comment and `CHANGELOG.md` as in §10; the tag message lists every change of the image (§12) | proposed | 01 |
| Z10 | Steps as in §11: the browser test and its control first, then the change | proposed | 01 |
| W1 | The browser test's tool: Playwright for Python, pinned with hashes, outside the image (§9.2) | open | 01 |

## 3. What IRIS 2.4.29 does

In the sources of IRIS 2.4.29 (`dfir-iris/iris-web` tag `v2.4.29`, commit `340ce040`, under
`source/`), whose files equal the base image's. The order's reading holds; these findings
shape the design.

- **The Overview's libraries.** The default layout loads DataTables 1.10.16; `overview.html`
  (lines 124–129) adds Responsive 2.2.9, SearchBuilder 1.5.0 and DateTime 1.5.0. Buttons
  1.6.1 and its column visibility plugin, which `includes/footer_case.html` loads for the case
  pages, are in the image under `assets/js/plugin/datatables/`. Once loaded, Buttons builds
  the `buttons` option of `overview.js` (lines 257–260) when the table initialises, and
  throws `Unknown button type: csvHtml5`, since the page does not load `buttons.html5.min.js`.
- **The filter fields.** `addFilterFields` clones the header row into a second one;
  `tableFiltering` (`datatablesUtils.js`, line 20) puts a field into the cell of that row at
  the position of the column's header among the visible ones. A column hidden at that moment
  has no position (`index()` of a detached cell is −1, and `.eq(-1)` takes the last visible
  cell), so it gets no field of its own. `removeFilter` (line 2) clears the input at the
  clicked cell's position among the table's inputs. Both serve every IRIS table with filter
  fields, the case tables included. On a visibility change, DataTables takes a hidden
  column's header cells out of the rows without emptying them, and puts them back when the
  column is shown (`_fnDrawHead`).
- **The notes editor.** `edit_innote()` (`case.notes.js`, line 596) toggles the editor,
  `#container_note_content`, and its toolbar, `#notes_edition_btn`, and widens the rendered
  view, `#ctrd_notesum`; `toggle_max_editor()` (line 540) hides the view and widens the
  editor. Hiding the editor while it is expanded therefore leaves both hidden. A note opens
  through `note_detail(id)` (line 372), which builds a new ACE editor each time; `add_note`
  (line 652) opens the note it created the same way. IRIS relays a note's change to every
  other session in the note's room, of any user (`skip_sid=request.sid`,
  `blueprints/case/case_notes_routes.py`, line 488).
- **Storage.** IRIS keeps its own choices per browser, in `localStorage` (`iris-tm-compact`,
  `iris-tm-tree`, `iris.statistics.state`, `iris.customDashboards.state`), and clears none
  of them at sign-out. The user table holds one column per server-side preference
  (`in_dark_mode`, `has_mini_sidebar`, …) and none for others.
- **The configuration.** `app/__init__.py` configures the root logger (line 65) before it
  loads `app.configuration.Config` into Flask's configuration (line 129), which templates
  read as `config`. The upstream compose passes `.env` to the app and to the worker
  (`env_file`). The app is gunicorn 20.1.0 with one eventlet worker; IRIS imports gunicorn
  nowhere, and the Celery worker imports the same application.
- **The cache.** The stock nginx proxies `/static` to the app, where Flask serves
  `app/static`, and gives it a lifetime of one year marked `immutable`, while pages get
  `no-store` (`docker/nginx/nginx.conf`, lines 113–130). `overview.html` (line 129) and
  `case_notes_v2.html` (line 235) name their scripts without a version, and are the only
  templates that name `overview.js` and `case.notes.js`.

## 4. Part A — the Overview's columns

### 4.1 The control (Z2)

- `overview.html` loads `dataTables.buttons.min.js` and `buttons.colVis.min.js`, the files
  the case pages load, and no other new script; Select's script stays unloaded, so
  `select: true` keeps having no effect. `overview.js` drops its `buttons` option (Export,
  Copy), which would otherwise throw (§3), so Export, Copy and row selection stay absent.
- A button with IRIS's column visibility icon (`fa-eye-slash`) and the title
  `Toggle columns`, as on the case tables, sits beside `Add filter`. It opens a list of the
  eleven columns but Title, in the table's order, each marked while visible and toggling its
  column; the last entry, `Default columns`, applies the defaults of §6 and forgets the
  choice.
- Title, the column of the case's link and its quick view, is in no list and stays visible.

### 4.2 The choice (Z1)

- Each toggle stores the visibility of the eleven columns in `localStorage`, under
  `iw2x.overview.columns`, as a JSON object keyed by the identifiers of §6.1
  (`{"outcome": true, "case_id": false, …}`). At each load of the Overview, a column takes its
  stored visibility, else its default; an entry that is not a boolean, an unknown key and an
  unreadable value are ignored, and a column that a later release adds takes its default.
- Per browser: a choice survives reloads, new visits and signing out and in. Another browser
  or browser profile, another host name or port for the same IRIS, a private window once it
  is closed, and clearing the site's data start from the defaults; the users of one browser
  profile share its choices, as they share IRIS's own (§3). Keeping a choice on the server
  would take a new column in the user table, a migration, which K11 rules out.

### 4.3 Filters and the rest (Z3)

- The table is initialised with every column visible: `initComplete` runs IRIS's own
  `tableFiltering`, so each column's filter cell gets its own field, and then applies the
  stored choice or the defaults. A hidden column's cell keeps its field (§3), so a column
  shown later brings its field back, still bound to its own column, and `removeFilter` finds
  it at its position. Hiding a column empties its field and clears its search.
  `datatablesUtils.js` stays stock.
- SearchBuilder's criteria stay as the user set them when a column is hidden: SearchBuilder
  filters on any column, visible or not, as it does on the three hidden columns in
  `2.4.29-2`.
- The data, sorting (at first by column 7, Tags, as in 2.4.29), paging, the switch between
  open and all cases, the quick view and the details row of a narrow window, which lists
  every column, hidden ones included, stay as they are.

## 5. Part B — the notes editor (Z4)

- The round button (`button.icon-note`, `onclick="edit_innote();"`) stays the control.
  `edit_innote()` shows or hides the editor as it does today and stores the result in
  `localStorage`, under `iw2x.notes.editor`, as `shown` or `hidden`: one choice for every
  note of every case. `toggle_max_editor()` stores nothing.
- `note_detail(id)` applies the stored choice, else the default of §6, once the note is
  loaded. `add_note` opens the note it created with its editor shown and leaves the stored
  choice as it is, so the next note opened takes the choice again.
- Hiding the editor while it is expanded first ends the expansion through
  `toggle_max_editor()`, so the view comes back and takes the width the editor leaves free,
  as `edit_innote()` gives it. Showing the editor brings back its toolbar and the widths as
  `edit_innote()` does, and has the ACE editor measure itself again (`note_editor.resize()`),
  since notes now often open with the editor hidden.
- Saving, the relay of changes between sessions, which goes on while the editor is hidden,
  and the note's history stay as they are.

## 6. Part C — defaults by configuration (Z5)

### 6.1 The variables

Read once per start from the process environment (`os.environ`, not IRIS's `config.load`,
which would also read the configuration file and a key vault), in `Config` of
`app/configuration.py`, which brings them into Flask's configuration. With the upstream
compose they go into `.env`.

| Variable | Value | Unset, empty or blank |
|---|---|---|
| `IW2X_OVERVIEW_COLUMNS` | the Overview's columns visible by default: identifiers separated by commas, spaces around them ignored, in any order; Title is visible whether listed or not | the columns 2.4.29 shows |
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

### 6.2 An unusable value

`IW2X_OVERVIEW_COLUMNS` holding an identifier outside the table, or commas and nothing
else, and `IW2X_NOTE_EDITOR` holding anything but `shown` or `hidden`, letter case
included, leave the default of 2.4.29 for what that variable sets; each variable is read on
its own.

### 6.3 The start log

In the app's log, after the entrypoint's version line and gunicorn's first lines, IRIS's
root logger writes in its own format one WARNING per unusable value, then one INFO line:

```
… :: WARNING :: configuration :: … :: iris-web-2x: IW2X_NOTE_EDITOR='maybe' cannot be used (expected 'shown' or 'hidden'); the default of 2.4.29 applies
… :: INFO :: configuration :: … :: iris-web-2x defaults: Overview columns title,customer,classification,state,tags,open_since,open_date,tasks,owner (2.4.29); note editor shown (2.4.29)
```

The INFO line lists the columns in the table's order and names where each default comes
from: the variable, or `2.4.29`. A value is written as Python's `repr`, so a line break in
it stays on the line. The reason for `IW2X_OVERVIEW_COLUMNS` is `unknown column '<id>'` or
`no column`. The lines come from the process gunicorn runs (`'gunicorn' in sys.modules`):
the Celery worker loads the same configuration, serves no page and writes neither.

### 6.4 The pages

The templates write the defaults into the page: `overview.html` as `data-iw2x-columns` on
`#overview_table` (the identifiers visible by default, Title included),
`case_notes_v2.html` as `data-iw2x-note-editor` on `#currentNoteContent`. The scripts read
them, and take the defaults of 2.4.29 when an attribute is missing or holds anything else.
A choice the user has made takes precedence (§4.2, §5).

## 7. The swap and the way back (Z6)

- The patched templates name the patched scripts
  `/static/assets/js/iris/overview.js?v=2.4.29-3` and
  `/static/assets/js/iris/case.notes.js?v=2.4.29-3`. Pages are never cached, so after the
  swap every browser loads the new pages, and with them URLs that no browser has cached. The
  vendor scripts the Overview now loads are stock files at their stock URLs.
- After a way back, the previous image's pages name the scripts without a version, and a
  browser takes them from its cache, filled by that image, or from that image. No page of
  `2.4.29-3` names a patched script at its old URL, so no browser can have cached new content
  there (§9.1). The stored choices stay in the browser, unused by the previous image, and
  apply again after a later swap.
- A later release that changes either script again changes its `v`.
- 2.4.29 and `2.4.29-2` serve the same two pages and scripts, so the test of the swap from
  `2.4.29-2` stands for the stock image too.

## 8. The patches (Z7)

| Patch | File, under `/iriswebapp` | Stock sha256 |
|---|---|---|
| `0008-configuration-ui-defaults.patch` | `app/configuration.py` | `53b2027e1c535c2bb2ab86f6c4fbab65079a69ad2477e8e8b217dba38184b820` |
| `0009-overview-columns-template.patch` | `app/blueprints/overview/templates/overview.html` | `f5eabe5fc12c474ee1302e11efa3f6293f47643604363d4ec625dcb76e6e34e6` |
| `0010-overview-columns-script.patch` | `app/static/assets/js/iris/overview.js` | `a177a4cd8f638f6be2f7f021fd4a58be802914ac643de7069a077d05fa291a72` |
| `0011-notes-editor-template.patch` | `app/blueprints/case/templates/case_notes_v2.html` | `a27f1fa18bbc74e7e333396d6c81bdef5dc39081906eeaf887712fa57f89b674` |
| `0012-notes-editor-script.patch` | `app/static/assets/js/iris/case.notes.js` | `894d458585c250f9f46bfddf18c918400f433ce6edba20c145d6e94450e5e280` |

The stock values are the tag's files and the base's, each mode `644`, owner `root:root`;
the base keeps no bytecode under `/iriswebapp/app`. They join `patches/stock.sha256`, and
the patched values `patches/patched.sha256`. The build checks both, as for the other
patches; `check-image.py` takes the patched files from `patched.sha256`, so its filesystem
check allows these five changes more, with their modes and owners kept, and nothing else.

## 9. Tests

### 9.1 Without a browser

`scripts/check-image.py` gains one check: no template under `/iriswebapp/app` names
`assets/js/iris/overview.js` or `assets/js/iris/case.notes.js` without a `?v=`. On the base it
finds the two references without one, and that is its control.

### 9.2 In a browser (Z8, W1)

`scripts/check-ui.py <image> --old <image>`, and `scripts/check-ui.py --control <image>`.

- **Stack.** The stock 2.4.29 database, as in `check-iris.sh`; the app of the image from its
  entrypoint; the stock 2.4.29 nginx,
  `ghcr.io/dfir-iris/iriswebapp_nginx@sha256:887b1eb8ceae5b1e1483a4a7601d79a6b070e314db5772a617e0a9190c556644`,
  with a certificate made for the run, published on `127.0.0.1` only. No worker and no
  broker: with no module enabled, nothing the run does queues a task. Secrets as in
  `check-iris.sh`: generated, masked, redacted. Containers and the network are named
  `iw2x-ui-<pid>-*` and removed with their volumes. Cases and notes are created through
  IRIS's API with the administrator's key.
- **Browser.** Headless Google Chrome as on the runner, or the Chromium-family browser
  `--browser` names, with persistent profiles in a temporary directory. The run's
  certificate is accepted by its key (`--ignore-certificate-errors-spki-list`), so the
  browser caches as for a trusted site; Chrome caches nothing loaded past an ignored
  certificate error. Driven by Playwright for Python, which
  `scripts/check-ui-requirements.txt` pins with hashes; CI installs it into a virtual
  environment on the runner, and a local run takes it with `uv run --with-requirements`.
- **Checks.** Each prints `ok` or `FAIL`, tagged `[new]`, which holds only with the change,
  or `[same]`, which holds on both images.

  | # | | Check |
  |---|---|---|
  | T1 | same | With no variable and no choice, the Overview shows the columns of 2.4.29 and a note opens with its editor |
  | T2 | same | A second load of the Overview and of the notes page takes their scripts from the browser's cache |
  | T3 | new | The Overview's control lists the eleven columns but Title, each marked as shown or hidden |
  | T4 | new | Outcome shown and Owner hidden through the control stay so after a reload, in a new tab, and after signing out and in |
  | T5 | new | `Default columns` brings back the defaults, and a reload keeps them |
  | T6 | new | A column shown later has its filter field, which filters its own column, and its clear button clears that field alone; hiding a column whose field filters empties the field and brings back the rows it hid |
  | T7 | same | The default columns' filter fields filter and clear their own columns; sorting, paging, SearchBuilder's `Add filter`, the switch to all cases and the quick view work; a narrow window's details row lists every column; there is no Export, no Copy and no row selection |
  | T8 | new | The editor hidden on one note stays hidden on another note, after a reload, and after signing out and in; shown again, likewise |
  | T9 | new | With the editor hidden by choice, a created note opens with its editor, and the next note opened takes the choice again |
  | T10 | new | With the editor expanded, hiding it leaves the rendered view shown, across the width |
  | T11 | same | With the editor shown, typing saves the note; a second session on the note, with its editor hidden, renders the first session's change; the note's history lists the revision |
  | T12 | new | With no variable set, the app's start log names the defaults of 2.4.29 |
  | T13 | new | With `IW2X_OVERVIEW_COLUMNS=title,case_id,severity,owner` and `IW2X_NOTE_EDITOR=hidden`, a profile without a choice gets them, a profile with one keeps it, and the start log names them |
  | T14 | new | With `IW2X_OVERVIEW_COLUMNS=title,bogus` and `IW2X_NOTE_EDITOR=maybe`, both pages show the defaults of 2.4.29, and the start log has the two warnings and the line |
  | T15 | same | After the way back to `--old`, in the profile used before it: no control, the columns and the editor of 2.4.29, the variables of T13 without effect |

- **Order.** The app first runs `--old`, where one profile loads both pages and T2 runs.
  Then the image under test, with no variable: in that same profile, which keeps its cache
  and its storage, T1 and T3–T11 run, so they also show §7's swap, and T12 reads the log.
  Then with the variables of T13, then with those of T14, each with a profile of its own
  beside the first; then `--old` again for T15, with the variables of T13 still set. nginx
  restarts after each change of the app, since it resolves the app's name once.
- **Result.** On the image under test every check passes. With `--control` the image is
  both the image under test and `--old`, and the run passes when every `[new]` check fails
  and every `[same]` check passes.
- **CI** runs `check-ui.py` on the built image with `--old` set to `2.4.29-2`, pinned by its
  registry digest
  (`ghcr.io/janwychowaniak/iris-web-2x@sha256:66d0e876b6384a22aff36e34a2538b1fac2da0b1be76bc74cc25865357fefeeb`),
  and `--control` on that image. The release runs the first, before it publishes. The
  `image` job's timeout grows to fit both runs.

### 9.3 The checks of today

Every check that CI runs on `main` at `b5c14a1` stays, and runs again on the built image.

## 10. Documentation (Z9)

- **README:** the list of what the image adds gains the Overview's columns and the notes
  editor, chosen by each user and remembered in the browser, with defaults set by the
  deployment ("six things" becomes seven); "Seven files of IRIS change" becomes twelve, and
  the table gains the five rows. A section on A, B and C: the control and the round button,
  the variables with their values and the identifiers, an unusable value and the start log's
  lines, when a choice is lost (§4.2), and the swap and the way back (§7). The list of checks
  names `check-ui.py`, its control and its tool. The release procedure gains one rule: a
  change of a script under `app/static` changes its `v` in the templates. The examples name
  `2.4.29-3`.
- **NOTICE:** "seven files" becomes twelve; the five are listed as this repository's own
  change.
- **Dockerfile:** the header comment names the Overview's columns and the notes editor; the
  `LABEL` description stays.
- **CHANGELOG.md:** the entry of `2.4.29-3`, with placeholders for the date, the digest, the
  image Id and the Python, the base digest, and the notes of §12.
- **VERSION:** `2.4.29-3`.

## 11. Steps (Z10)

Each step ends with a `reply-NN.md`; the consumer verifies it and answers.

1. After the go: `scripts/check-ui.py` and its requirements, run locally with `--control`
   on `2.4.29-2`, before anything of the change exists: every `[new]` check fails, every
   `[same]` check passes.
2. The patches and their checksums, the check of §9.1, `VERSION`, the documentation of §10,
   and the steps of §9.2 in `ci.yml` and `release.yml`; a local classic build, every CI
   script run locally on it, `check-ui.py` with `--old` on `2.4.29-2`, and its control. The
   consumer then accepts the local build (K2–K7, K11, K12).
3. On the owner's word, the push; CI green on GitHub on that commit; the tag message shown
   to the owner.
4. The tag on the owner's word, the release, the owner's commit of the published values,
   the consumer's acceptance of the published image and the archive (K1–K3, K5, K8–K10), and
   the removal of this file.

## 12. The tag message, to be (Z9)

```
iris-web-2x 2.4.29-3

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
- the Overview's columns, shown or hidden by each user and remembered in the browser, with
  the defaults set by IW2X_OVERVIEW_COLUMNS;
- a note's editor, shown or hidden as the user last left it and remembered in the browser,
  with the default set by IW2X_NOTE_EDITOR;
- the image version in labels, in /usr/share/doc/iris-web-2x/VERSION and in the start log.
```
