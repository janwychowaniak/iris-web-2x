#!/usr/bin/env python3
"""Prove that each worker patch carries upstream's lines byte for byte (SPEC §4.2, O3).

For every patch below, the sequence of lines it removes and the sequence of lines it adds
must equal those of its upstream commit's change to the named file. The context lines are
2.4.29's and are not compared. The upstream commits are fetched from github.com, two deep so
that each has its parent.

    check-upstream-lines.py [<repository root>]
"""
import pathlib
import subprocess
import sys
import tempfile

UPSTREAM = "https://github.com/dfir-iris/iris-backend"
PATCHES = [
    ("patches/0001-module-handler-reset-session.patch",
     "294ed4a19bf7cfe60c75f20cacdbc79d91ce6a9f",
     "source/app/iris_engine/module_handler/module_handler.py"),
    ("patches/0002-tasks-worker-process-init.patch",
     "9098c754089d28e9ebe448fb37a9ae55403b8b7e",
     "source/app/iris_engine/tasker/tasks.py"),
]


def changed_lines(diff: bytes):
    """The removed and the added lines of a one-file unified diff, without their marker."""
    removed, added, in_hunk = [], [], False
    for line in diff.split(b"\n"):
        if line.startswith(b"@@"):
            in_hunk = True
        elif in_hunk and line.startswith(b"-"):
            removed.append(line[1:])
        elif in_hunk and line.startswith(b"+"):
            added.append(line[1:])
        elif line.startswith(b"diff --git"):
            in_hunk = False
    return removed, added


def main() -> int:
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    failed = False
    with tempfile.TemporaryDirectory() as repo:
        git = ["git", "-C", repo]
        subprocess.run(git + ["init", "-q"], check=True)
        for _, commit, _ in PATCHES:
            subprocess.run(git + ["fetch", "-q", "--depth=2", UPSTREAM, commit], check=True)
        for patch, commit, path in PATCHES:
            upstream = subprocess.run(git + ["show", "--format=", commit, "--", path],
                                      check=True, capture_output=True).stdout
            ours = (root / patch).read_bytes()
            up_rem, up_add = changed_lines(upstream)
            our_rem, our_add = changed_lines(ours)
            if not up_rem and not up_add:
                print(f"FAIL {patch}: {commit[:8]} changes nothing in {path}")
                failed = True
            elif (our_rem, our_add) != (up_rem, up_add):
                print(f"FAIL {patch}: its changed lines differ from {commit[:8]} {path}")
                failed = True
            else:
                print(f"ok   {patch}: -{len(our_rem)} +{len(our_add)} lines equal {commit[:8]} {path}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
