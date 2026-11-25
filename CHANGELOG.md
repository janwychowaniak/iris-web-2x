# Changelog

The release notes are the annotated tag messages. This file carries the same
notes where they can be read without git, together with, for each version, the
image digest it was published under, its image Id (configuration digest), the
Python it runs and the digest of its base, and corrections to them as errata.

**A tag is never pushed again, not even to fix its message.** Pushing it runs
the release again and can publish the same version under a different digest,
which breaks the one property a pinned deployment stands on. A wrong line in a
tag message is corrected here instead, as an erratum that says what the tag
claims and what is true.

The image Id is what a host compares after `docker load` of a release file. On
Docker's default `overlay2` image store, it is the digest of the image's
configuration, which the archive carries byte for byte (see the README).

## 2.4.29-2 — 2026-11-25

`ghcr.io/janwychowaniak/iris-web-2x@sha256:66d0e876b6384a22aff36e34a2538b1fac2da0b1be76bc74cc25865357fefeeb`

Image Id (configuration digest)
`sha256:f7bb8c35888ee154106864f4034b1f026fb9a67a8627a3a8cbedfb7fe037690c`, after
a pull and after `docker load` of the release file alike. Python 3.9.25. Base
`ghcr.io/dfir-iris/iriswebapp_app@sha256:d7d23026bdde593278075821d3abc8649fe28d618d5784cc9875bd7a3d05699b`.

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

## 2.4.29-1 — 2026-11-24

`ghcr.io/janwychowaniak/iris-web-2x@sha256:56c58f51e3ccff58cc9822fc69d91faecf0ace53033fb22c786f0ec2a0044374`

Image Id (configuration digest)
`sha256:02e5dfc012982572b6407fdb1f13bb30a794552a3b90b17c5ff0516e82ec7ad9`, after
a pull and after `docker load` of the release file alike. Python 3.9.25. Base
`ghcr.io/dfir-iris/iriswebapp_app@sha256:d7d23026bdde593278075821d3abc8649fe28d618d5784cc9875bd7a3d05699b`.

DFIR-IRIS 2.4.29 (ghcr.io/dfir-iris/iriswebapp_app@sha256:d7d23026bdde593278075821d3abc8649fe28d618d5784cc9875bd7a3d05699b) with:
- the Celery worker's pool children drop the database session and connections inherited
  from their parent: iris-backend 294ed4a1 and the tasks.py change of 9098c754;
- IrisFacadeRenderer 0.2.0 built in: state by badge classes, ENVELOPE.md v1 only,
  an unrecognised value shown as "?" without stopping the other tabs;
- IrisWebHooks 1.0.9+jw.2 (fork) in place of 1.0.9;
- the attribute tab buttons of IRIS's modals open their panes under its Bootstrap 4.6.2,
  whatever the tab's name;
- the image version in labels, in /usr/share/doc/iris-web-2x/VERSION and in the start log.
