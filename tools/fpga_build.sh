#!/usr/bin/env bash
# Synthesize + place-and-route the board self-test, the same way docs/fpga-results.txt was made.
#   tools/fpga_build.sh ecp5  [kernel]    # Lattice ECP5-25K, 4 lanes   (ULX3S, Colorlight)
#   tools/fpga_build.sh ice40 [kernel]    # Lattice iCE40 UP5K, 2 lanes (iCEBreaker)
# Needs: yosys, nextpnr-ecp5 / nextpnr-ice40. Add --lpf/--pcf for your board's pins to get a flashable bitstream.
set -euo pipefail
cd "$(dirname "$0")/.."
target=${1:?ecp5 or ice40}; kernel=${2:-matmul}
if [ "$target" = ice40 ]; then
  [ "$kernel" = matmul ] && kernel=mesh_volume   # 2-lane builds need a linearly indexed kernel
  python3 tools/fpga_image.py "$kernel" --lanes 2
  yosys -q -p "read_verilog -Ihw -Ibuild hw/gpu.v hw/fpga_top.v; synth_ice40 -dsp -top fpga_top -json build/top.json; stat"
  nextpnr-ice40 --up5k --package sg48 --json build/top.json --freq 12 --timing-allow-fail
else
  python3 tools/fpga_image.py "$kernel"
  yosys -q -p "read_verilog -Ihw -Ibuild hw/gpu.v hw/fpga_top.v; synth_ecp5 -top fpga_top -json build/top.json; stat"
  nextpnr-ecp5 --25k --package CABGA381 --json build/top.json --freq 20 --timing-allow-fail
fi
