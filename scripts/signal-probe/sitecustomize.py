"""A test-only probe for scripts/check-iris.sh, never part of the image: a worker container
loads it through PYTHONPATH from a read-only mount.

In each forked child of a process that has already imported Celery's signals, it connects
two worker_process_init handlers, after the image's own (patch 0002's). The first writes
"iw2x-signal-probe raising <process name>" to fd 2, outside logging, and raises
RuntimeError("iw2x-signal-probe <process name>"); the second writes
"iw2x-signal-probe after <process name>" the same way. Celery's Signal.send calls the
receivers in the order they were connected and logs a receiver's exception before it calls
the next one, so its line "Signal handler <...> raised: RuntimeError('iw2x-signal-probe
<process name>')", if logging lets it through, comes between the two markers. It imports
nothing at start and nothing new in the child.
"""
import os
import sys


def _write(line):
    os.write(2, (line + "\n").encode())


def _after_fork_in_child():
    signals = sys.modules.get("celery.signals")
    process = sys.modules.get("billiard.process")
    if signals is None or process is None:
        return

    def raising(**kwargs):
        name = process.current_process().name
        _write("iw2x-signal-probe raising %s" % name)
        raise RuntimeError("iw2x-signal-probe %s" % name)

    def after(**kwargs):
        _write("iw2x-signal-probe after %s" % process.current_process().name)

    signals.worker_process_init.connect(raising, weak=False)
    signals.worker_process_init.connect(after, weak=False)


os.register_at_fork(after_in_child=_after_fork_in_child)
