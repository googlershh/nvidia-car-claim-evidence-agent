"""Run deploy_nemoclaw.ipynb headless with IPython, skipping provider cells (a) and (b).

Provider (c) build.nvidia.com is used; NVIDIA_API_KEY comes from the environment
(cell 12 falls back to it when the cell value is blank). NEMOCLAW_MODEL is left blank
so NemoClaw keeps its default model (Nemotron 3 Super).
"""
import json
import sys
from pathlib import Path

from IPython.core.interactiveshell import InteractiveShell

NB = Path.home() / "video-search-and-summarization/deploy/docker/scripts/deploy_nemoclaw.ipynb"
SKIP = {6, 8}                # (a) OpenAI-compatible endpoint, (b) NemoClaw-managed local model
# --after-onboard: the sandbox already exists; skip Docker pinning (16) and install/onboard (21)
if "--after-onboard" in sys.argv:
    SKIP |= {16, 21}
OVERRIDE = {10: {"NEMOCLAW_MODEL": ""}}

nb = json.loads(NB.read_text())
shell = InteractiveShell.instance()
shell.run_cell(f"import os; os.chdir({str(NB.parent)!r})")
for i, cell in enumerate(nb["cells"]):
    if cell["cell_type"] != "code" or i in SKIP:
        continue
    src = "".join(cell["source"])
    print(f"\n########## cell {i}: {src.strip().splitlines()[0][:90]}", flush=True)
    res = shell.run_cell(src)
    for name, value in OVERRIDE.get(i, {}).items():
        shell.user_ns[name] = value
        print(f"[override] {name} = {value!r}", flush=True)
    if not res.success:
        print(f"########## FAILED at cell {i}", flush=True)
        sys.exit(1)
print("\n########## ALL CELLS DONE", flush=True)
