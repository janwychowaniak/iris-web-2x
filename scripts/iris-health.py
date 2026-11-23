"""Runs inside a container of the image, against the stock 2.4.29 database (check-iris.sh):
python - < scripts/iris-health.py, from /iriswebapp.

Importing IRIS runs its post-init, which sets the database up and registers IRIS's default
modules. IRIS catches a failed post-init and only logs it, so the registration it leaves
is checked: the fork registered by IRIS itself, disabled, with its version (SPEC §6), and
the renderer not registered (O8). Then IRIS's own health check, on instances created by
instantiate_module_from_name, must pass for both modules.
"""
import sys

from app import app  # post-init runs on this import
from app.iris_engine.module_handler.module_handler import check_module_health
from app.iris_engine.module_handler.module_handler import instantiate_module_from_name
from app.models import IrisModule

failed = []


def report(ok, name, detail=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok or not detail else ": " + detail), flush=True)
    if not ok:
        failed.append(name)


with app.app_context():
    fork = IrisModule.query.filter_by(module_name="iris_webhooks_module").first()
    renderer = IrisModule.query.filter_by(module_name="iris_facade_renderer_module").first()
    found = None if fork is None else (fork.module_version, fork.is_active)
    report(found == ("1.0.9+jw.2", False),
           "post-init registered iris_webhooks_module 1.0.9+jw.2, disabled",
           "found %s" % (found,))
    report(renderer is None, "post-init left iris_facade_renderer_module unregistered")

    # A module's constructor reads IRIS's settings, so it needs the application context too,
    # as it has in IRIS's own request or task.
    for name in ("iris_webhooks_module", "iris_facade_renderer_module"):
        result = instantiate_module_from_name(name)
        instance = result[0] if isinstance(result, tuple) else result  # a bare None on two paths
        healthy, logs = check_module_health(instance)
        report(bool(healthy), "%s passes check_module_health" % name, "; ".join(map(str, logs)))

sys.exit(1 if failed else 0)
