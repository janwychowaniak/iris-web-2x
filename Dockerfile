# iris-web-2x: the stock DFIR-IRIS 2.4.29 application image plus two upstream worker
# fixes, the IrisWebHooks fork and the image's own version (SPEC.md). Builds with the
# classic builder (DOCKER_BUILDKIT=0); scripts/build.sh passes the build arguments.

# The OCI index of ghcr.io/dfir-iris/iriswebapp_app:v2.4.29.
FROM ghcr.io/dfir-iris/iriswebapp_app@sha256:d7d23026bdde593278075821d3abc8649fe28d618d5784cc9875bd7a3d05699b

ARG IMAGE_VERSION
ARG REVISION
ARG CREATED

LABEL org.opencontainers.image.title="iris-web-2x" \
      org.opencontainers.image.description="DFIR-IRIS 2.4.29 with two upstream worker fixes and two modules built in" \
      org.opencontainers.image.version="${IMAGE_VERSION}" \
      org.opencontainers.image.revision="${REVISION}" \
      org.opencontainers.image.created="${CREATED}" \
      org.opencontainers.image.source="https://github.com/janwychowaniak/iris-web-2x" \
      org.opencontainers.image.url="https://github.com/janwychowaniak/iris-web-2x" \
      org.opencontainers.image.licenses="LGPL-3.0-or-later" \
      org.opencontainers.image.base.name="ghcr.io/dfir-iris/iriswebapp_app:v2.4.29" \
      org.opencontainers.image.base.digest="sha256:d7d23026bdde593278075821d3abc8649fe28d618d5784cc9875bd7a3d05699b"

COPY . /tmp/iris-web-2x/

# One step, so the build files never reach a layer of their own. Every check fails the build.
RUN set -eu; \
    b=/tmp/iris-web-2x; doc=/usr/share/doc/iris-web-2x; \
    # No Python run here may leave bytecode outside the installed packages: the base keeps
    # none for the standard library, which pip and setup.py import.
    export PYTHONDONTWRITEBYTECODE=1; \
    test -n "${IMAGE_VERSION}"; test -n "${REVISION}"; test -n "${CREATED}"; \
    \
    # The version: one declaration, and its base part is the base's IRIS version.
    test "$(cat "$b/VERSION")" = "${IMAGE_VERSION}"; \
    grep -Eq "^ *IRIS_VERSION = \"v${IMAGE_VERSION%-*}\"" /iriswebapp/app/configuration.py; \
    install -d -m 0755 "$doc"; \
    install -m 0644 "$b/VERSION" "$b/LICENSE" "$b/COPYING" "$b/NOTICE" "$doc/"; \
    \
    # Part A and the start line: stock files in, patched files out, mode kept.
    cd /iriswebapp; \
    sha256sum -c "$b/patches/stock.sha256"; \
    for p in "$b"/patches/*.patch; do \
        patch -p1 --forward --fuzz=0 --no-backup-if-mismatch < "$p"; \
    done; \
    sha256sum -c "$b/patches/patched.sha256"; \
    test "$(stat -c '%a %U:%G' iris-entrypoint.sh)" = "755 root:root"; \
    \
    # Part C: the fork at its annotated tag, on the commit the order names.
    git -c advice.detachedHead=false clone --quiet --depth 1 --branch 'v1.0.9+jw.2' \
        https://github.com/janwychowaniak/iris-webhooks-module "$b/fork"; \
    test "$(git -C "$b/fork" cat-file -t 'refs/tags/v1.0.9+jw.2')" = tag; \
    test "$(git -C "$b/fork" rev-parse 'refs/tags/v1.0.9+jw.2^{commit}')" = 8b30028ee6ec580b2404cccacb49db300eec197e; \
    pip install --quiet --no-deps --no-index --no-cache-dir "$b/fork"; \
    test "$(pip show iris_webhooks_module | sed -n 's/^Version: //p')" = '1.0.9+jw.2'; \
    # Its bytecode, as the stock 1.0.9 had; compileall writes it whatever the variable says.
    site=$(python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])'); \
    python -m compileall -q "$site/iris_webhooks_module"; \
    \
    cd /; rm -rf "$b"
