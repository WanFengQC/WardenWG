from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

MARK_BEGIN = "# managed-by=wardenwg begin"
MARK_END = "# managed-by=wardenwg end"


def replace_managed_block(original: str, managed_block: str) -> str:
    pattern = re.compile(
        rf"{re.escape(MARK_BEGIN)}.*?{re.escape(MARK_END)}",
        flags=re.DOTALL,
    )
    if pattern.search(original):
        return pattern.sub(managed_block.strip(), original)
    if not original.endswith("\n"):
        original += "\n"
    return f"{original}\n{managed_block.strip()}\n"


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: python3 wardenwg_merge_peers.py <wg_name> <managed_snippet>", file=sys.stderr)
        return 1

    wg_name = sys.argv[1]
    managed_path = Path(sys.argv[2])
    target = Path(f"/etc/wireguard/{wg_name}.conf")
    temp = Path(f"/etc/wireguard/{wg_name}.conf.tmp")

    original = target.read_text(encoding="utf-8")
    managed_block = managed_path.read_text(encoding="utf-8")
    merged = replace_managed_block(original, managed_block)

    temp.write_text(merged, encoding="utf-8")
    subprocess.run(["wg-quick", "strip", str(temp)], check=True, capture_output=True)
    subprocess.run(["wg", "syncconf", wg_name, str(temp)], check=True)
    target.write_text(merged, encoding="utf-8")
    temp.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
