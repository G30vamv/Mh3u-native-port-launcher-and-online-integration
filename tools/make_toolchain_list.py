#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Write launcher/assets/toolchain_files.txt: the files of a trimmed LLVM-MinGW the port needs.

    python tools/make_toolchain_list.py "<launcher folder>/toolchain" launcher/assets/toolchain_files.txt

Run it again (on a toolchain that still compiles the port) whenever LLVM_MINGW_URL changes.
"""
import os
import sys

root, out = sys.argv[1], sys.argv[2]
names = []
for r, _, files in os.walk(root):
    for f in files:
        names.append(os.path.relpath(os.path.join(r, f), root).replace(os.sep, "/"))
names.sort()
with open(out, "w", encoding="utf-8", newline="\n") as fh:
    fh.write("\n".join(names) + "\n")
print(f"{len(names)} files -> {out}")
