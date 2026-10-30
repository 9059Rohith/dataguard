"""Add official cross-platform archive hashes to an initialized provider lock.

The Windows provider was SHA256-verified before extraction by the parent task.
Archive hashes here come directly from the official HTTPS release checksum file;
they allow Linux CI to verify its own downloaded provider without a second huge
local Linux binary download. No provider binary or cloud credential is embedded.
"""

from pathlib import Path

lock = Path("infra/.terraform.lock.hcl")
checksums = Path("evidence/provider-sha256sums.txt")
value = lock.read_text(encoding="utf-8")
hashes = [
    line.split()[0]
    for line in checksums.read_text().splitlines()
    if line.split()[1].endswith(".zip")
]
for digest in hashes:
    entry = f'    "zh:{digest}",\n'
    if entry.strip() not in value:
        value = value.replace("  hashes = [\n", "  hashes = [\n" + entry)
lock.write_text(value, encoding="utf-8", newline="\n")
