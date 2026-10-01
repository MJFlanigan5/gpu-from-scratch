#!/usr/bin/env python3
"""Build the ROM images for hw/fpga_top.v from a kernel.

    python tools/fpga_image.py vector_add [--lanes 4]

Writes build/fpga_prog.hex, build/fpga_data.hex, build/fpga_expect.hex and
build/fpga_params.vh. The expected answers come from the reference model, so
a board that lights led_pass computed exactly what the simulator did.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from asm import assemble  # noqa: E402
import refsim  # noqa: E402
from run import KERNELS, ROOT, load_kernel  # noqa: E402

# Where each kernel writes its answers (address, count).
RESULT_REGION = {
    "vector_add": (64, 8),
    "matmul": (32, 16),
    "relu_layer": (24, 4),
    "mesh_volume": (200, 12),
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("kernel", choices=sorted(RESULT_REGION))
    p.add_argument("--lanes", type=int, default=4)
    args = p.parse_args()

    # Kernels that index with blockIdx*blockDim+threadIdx can run at any lane
    # count (grid rescaled); the others assume 4 lanes per block.
    if args.lanes != 4 and args.kernel not in ("vector_add", "mesh_volume"):
        sys.exit(f"{args.kernel} assumes 4 lanes per block")
    kernel = load_kernel(args.kernel)
    program = assemble((KERNELS / f"{args.kernel}.asm").read_text())
    image = [0] * refsim.DMEM_WORDS
    for addr, val in kernel.setup().items():
        image[addr] = val
    grid = kernel.GRID * 4 // args.lanes
    res = refsim.run(program, image, grid, args.lanes)
    if res.error:
        sys.exit(f"kernel fails on the reference model with {args.lanes} lanes: {res.notes}")

    base, count = RESULT_REGION[args.kernel]
    ndata = max(i for i, v in enumerate(image) if v) + 1 if any(image) else 1
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    hexes = {"prog": program, "data": image[:ndata], "expect": res.mem[base:base + count]}
    for name, words in hexes.items():
        (build / f"fpga_{name}.hex").write_text("".join(f"{w & 0xFFFFFFFF:08x}\n" for w in words))
    (build / "fpga_params.vh").write_text(
        f"`define FPGA_NLANES {args.lanes}\n`define FPGA_GRID {grid}\n"
        f"`define FPGA_NPROG {len(program)}\n`define FPGA_NDATA {ndata}\n"
        f"`define FPGA_EXP_BASE {base}\n`define FPGA_NEXP {count}\n")
    print(f"{args.kernel}: {len(program)} instructions, {ndata} data words, "
          f"checking {count} results at {base}, {args.lanes} lanes")


if __name__ == "__main__":
    main()
