#!/usr/bin/env python3
"""Assemble a kernel, run it on the Verilog GPU (Icarus) and on the Python
reference model, check they agree event-for-event, then check the answer.

    python tools/run.py matmul                  # run one kernel
    python tools/run.py --all                   # run every kernel
    python tools/run.py matmul --trace          # print every instruction, every lane
    python tools/run.py matmul --html out.html  # step-through viewer in your browser
    python tools/run.py matmul --backend ref    # no Verilog simulator needed
"""

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from asm import assemble  # noqa: E402
from isa import disasm, to_signed32  # noqa: E402
import refsim  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
KERNELS = ROOT / "kernels"
BUILD = ROOT / "build"
LANES = 4


def load_kernel(name):
    spec = importlib.util.spec_from_file_location(name, KERNELS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build_sim():
    if not shutil.which("iverilog"):
        sys.exit("iverilog not found — install Icarus Verilog, or use --backend ref")
    BUILD.mkdir(exist_ok=True)
    out = BUILD / f"sim_{LANES}.vvp"
    srcs = [ROOT / "hw" / "gpu.v", ROOT / "hw" / "tb.v"]
    if not out.exists() or any(s.stat().st_mtime > out.stat().st_mtime for s in srcs + [ROOT / "hw" / "isa.vh"]):
        subprocess.run(["iverilog", "-g2012", "-DTRACE", f"-DNLANES={LANES}", "-I", str(ROOT / "hw"),
                        "-o", str(out), *map(str, srcs)], check=True)
    return out


def run_hw(name, program, mem_image, grid):
    sim = build_sim()
    prog_hex, data_hex, out_hex = (BUILD / f"{name}.{s}.hex" for s in ("prog", "data", "out"))
    prog_hex.write_text("".join(f"{w:08x}\n" for w in program))
    data_hex.write_text("".join(f"{v & 0xFFFFFFFF:08x}\n" for v in mem_image))
    proc = subprocess.run(["vvp", "-n", str(sim), f"+prog={prog_hex}", f"+data={data_hex}",
                           f"+out={out_hex}", f"+grid={grid}"], capture_output=True, text=True, check=True)
    events, result = [], None
    for line in proc.stdout.splitlines():
        if line.startswith("T "):
            kv = dict(re.findall(r"(\w+)=(-?\w+)", line))
            kind = line.split()[2]
            if kind == "EXEC":
                events.append(("EXEC", int(kv["blk"]), int(kv["pc"]), int(kv["instr"], 16)))
            elif kind == "WB":
                events.append(("WB", int(kv["lane"]), int(kv["rd"]), int(kv["val"])))
            elif kind == "LD":
                events.append(("LD", int(kv["lane"]), int(kv["rd"]), int(kv["addr"]), int(kv["val"])))
            elif kind == "ST":
                events.append(("ST", int(kv["lane"]), int(kv["addr"]), int(kv["val"])))
            elif kind == "BR":
                events.append(("BR", int(kv["taken"]), int(kv["divergent"])))
        elif line.startswith("RESULT"):
            result = {k: int(v) for k, v in re.findall(r"(\w+)=(\d+)", line)}
    if result is None:
        sys.exit(f"simulator produced no RESULT line:\n{proc.stdout}\n{proc.stderr}")
    lines = [ln.split("//")[0].strip() for ln in out_hex.read_text().splitlines()]
    mem = [to_signed32(int(x, 16)) for ln in lines for x in ln.split()]
    return mem, events, result


def describe(ev):
    kind = ev[0]
    if kind == "WB":
        return f"      lane {ev[1]}: r{ev[2]} = {ev[3]}"
    if kind == "LD":
        return f"      lane {ev[1]}: r{ev[2]} = mem[{ev[3]}] -> {ev[4]}"
    if kind == "ST":
        return f"      lane {ev[1]}: mem[{ev[2]}] = {ev[3]}"
    if kind == "BR":
        return "      branch " + ("DIVERGED" if ev[2] else ("taken" if ev[1] else "not taken"))
    return ""


def print_trace(events):
    for ev in events:
        if ev[0] == "EXEC":
            print(f"  block {ev[1]}  pc {ev[2]:3d}  {disasm(ev[3])}")
        else:
            print(describe(ev))


def viewer_payload(name, kernel, program, mem_image, events, stats):
    steps = []
    for ev in events:
        if ev[0] == "EXEC":
            steps.append({"block": ev[1], "pc": ev[2], "asm": disasm(ev[3]), "ev": []})
        elif steps:
            steps[-1]["ev"].append(list(ev))
    return {
        "name": name, "title": kernel.TITLE, "lanes": LANES,
        "program": [disasm(w) for w in program],
        "mem": {i: v for i, v in enumerate(mem_image) if v},
        "steps": steps, "stats": stats,
    }


def write_html(path, payloads, fragment=False):
    page = (ROOT / "tools" / "viewer.html").read_text().replace("/*__DATA__*/null", json.dumps(payloads))
    if not fragment:  # standalone file you can double-click
        page = ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width, initial-scale=1"></head><body>\n'
                + page + "\n</body></html>\n")
    Path(path).write_text(page)


def run_kernel(name, backend, trace=False):
    kernel = load_kernel(name)
    program = assemble((KERNELS / f"{name}.asm").read_text())
    image = [0] * refsim.DMEM_WORDS
    for addr, val in kernel.setup().items():
        image[addr] = val
    expect_error = getattr(kernel, "EXPECT_ERROR", False)

    ref = refsim.run(program, image, kernel.GRID, LANES)
    if backend == "ref":
        mem, events, error, cycles = ref.mem, ref.events, ref.error, ref.cycles
    else:
        mem, events, result = run_hw(name, program, image, kernel.GRID)
        error, cycles = bool(result["error"]), result["cycles"]
        if events != ref.events:
            n = max(len(events), len(ref.events))
            first = next(i for i in range(n) if events[i:i + 1] != ref.events[i:i + 1])
            sys.exit(f"[{name}] HARDWARE != REFERENCE at event {first}: "
                     f"hw={events[first:first + 1]} ref={ref.events[first:first + 1]}")
        if cycles != ref.cycles:
            sys.exit(f"[{name}] cycle count mismatch: hw={cycles} ref={ref.cycles}")
        if not error and mem[:len(ref.mem)] != ref.mem:
            sys.exit(f"[{name}] final memory differs between hardware and reference")

    print(f"\n=== {name}: {kernel.TITLE}")
    print(f"    {kernel.GRID} block(s) x {LANES} lanes = {kernel.GRID * LANES} threads, "
          f"{len(program)} instructions in the program")
    if trace:
        print_trace(events)
    alu = ref.lane_ops
    print(f"    {ref.instructions} instructions issued, {alu} ALU lane-operations, {cycles} cycles "
          f"({ref.mem_cycles} of them waiting on the memory port)")
    if backend != "ref":
        print("    hardware matched the reference model on every register write, load, store and branch")

    if expect_error:
        ok = error
        print(f"    {'PASS' if ok else 'FAIL'}: {kernel.check(mem)[1] if ok else 'expected an error, got none'}")
        for note in ref.notes:
            print(f"    note: {note}")
    elif error:
        ok = False
        print(f"    FAIL: core reported an error {ref.notes}")
    else:
        ok, msg = kernel.check(mem)
        print(f"    {'PASS' if ok else 'FAIL'}: {msg}")

    stats = {"instructions": ref.instructions, "lane_ops": alu, "cycles": cycles,
             "mem_cycles": ref.mem_cycles, "grid": kernel.GRID, "backend": backend}
    return ok, viewer_payload(name, kernel, program, image, events, stats)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("kernel", nargs="?")
    p.add_argument("--all", action="store_true")
    p.add_argument("--backend", choices=["hw", "ref"], default="hw")
    p.add_argument("--trace", action="store_true")
    p.add_argument("--html", help="write a step-through viewer (all kernels with --all)")
    p.add_argument("--fragment", action="store_true", help=argparse.SUPPRESS)
    args = p.parse_args()
    names = sorted(f.stem for f in KERNELS.glob("*.asm")) if args.all else [args.kernel]
    if not names[0]:
        p.error("name a kernel or pass --all")
    runs = [run_kernel(n, args.backend, args.trace) for n in names]
    results = [ok for ok, _ in runs]
    if args.html:
        write_html(args.html, [payload for _, payload in runs], args.fragment)
        print(f"\nviewer written to {args.html} — open it in a browser")
    print(f"\n{sum(results)}/{len(results)} kernel(s) passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
