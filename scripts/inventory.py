"""Print one line per filesystem entry: path, type, mode, owner, size, and sha256 or link target.

Runs inside a container of an image, without network: python3 -I -B - < scripts/inventory.py.
It writes nothing but stdout. Skipped: the kernel's filesystems and the files the container
runtime puts in every container. check-image.py compares the base's listing with the image's.
"""
import hashlib, os, stat, sys

SKIP_DIRS = {"/proc", "/sys", "/dev"}
SKIP_FILES = {"/etc/hostname", "/etc/hosts", "/etc/resolv.conf", "/.dockerenv"}
out = sys.stdout

def digest(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

for root, dirs, files in os.walk("/", topdown=True):
    dirs[:] = sorted(d for d in dirs if os.path.join(root, d) not in SKIP_DIRS)
    for name in sorted(dirs) + sorted(files):
        p = os.path.join(root, name)
        if p in SKIP_FILES:
            continue
        st = os.lstat(p)
        m = st.st_mode
        if stat.S_ISLNK(m):
            kind, extra = "l", os.readlink(p)
        elif stat.S_ISDIR(m):
            kind, extra = "d", ""
        elif stat.S_ISREG(m):
            kind, extra = "f", digest(p)
        else:
            kind, extra = "o", ""
        size = st.st_size if kind == "f" else 0
        out.write(f"{p}\t{kind}\t{stat.S_IMODE(m):o}\t{st.st_uid}:{st.st_gid}\t{size}\t{extra}\n")
