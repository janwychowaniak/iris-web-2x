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

## 2.4.29-1 — (pending: the date of the tag)

`ghcr.io/janwychowaniak/iris-web-2x@sha256:` (pending: from the release
workflow's step summary)

Image Id (configuration digest) `sha256:` (pending), after a pull and after
`docker load` of the release file alike. Python (pending). Base
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
