"""Run with:  python -m pytest -q"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from asm import AsmError, assemble  # noqa: E402
from isa import OPCODES, decode, disasm  # noqa: E402
import refsim  # noqa: E402

KERNELS = sorted(p.stem for p in (ROOT / "kernels").glob("*.asm"))
HAVE_IVERILOG = shutil.which("iverilog") is not None


def test_isa_header_matches_python():
    """hw/isa.vh and tools/isa.py must agree on every opcode."""
    header = (ROOT / "hw" / "isa.vh").read_text()
    in_verilog = {m[0].lower(): int(m[1], 16) for m in re.findall(r"`define OP_(\w+)\s+6'h([0-9A-Fa-f]+)", header)}
    assert in_verilog == {name: code for name, (code, _) in OPCODES.items()}


def test_assemble_disassemble_roundtrip():
    src = "li r1, -5\nadd r2, r1, r1\nld r3, 16(r2)\nsreg r4, blockIdx\nloop:\nbnz r4, loop\nhalt\n"
    words = assemble(src)
    assert [disasm(w) for w in words] == [
        "li r1, -5", "add r2, r1, r1", "ld r3, 16(r2)", "sreg r4, blockIdx", "bnz r4, 4", "halt"]
    assert decode(words[0]).imm == -5


@pytest.mark.parametrize("bad", ["add r1, r2", "foo r1", "li r16, 1", "ld r1, r2", "bnz r1, nowhere"])
def test_assembler_rejects_bad_input(bad):
    with pytest.raises(AsmError):
        assemble(bad)


def test_reference_arithmetic_wraps_like_hardware():
    prog = assemble("li r1, 65536\nmul r2, r1, r1\nli r3, -256\nsra r4, r3, 4\nst r2, 0(r0)\nst r4, 1(r0)\nhalt")
    res = refsim.run(prog, [], grid=1, lanes=1)
    assert res.mem[0] == 0           # 2^32 wraps to 0 in 32 bits
    assert res.mem[1] == -16         # arithmetic shift keeps the sign


@pytest.mark.parametrize("name", KERNELS)
def test_kernel_on_reference_model(name):
    run = subprocess.run([sys.executable, ROOT / "tools" / "run.py", name, "--backend", "ref"],
                         capture_output=True, text=True)
    assert run.returncode == 0, run.stdout + run.stderr


@pytest.mark.skipif(not HAVE_IVERILOG, reason="Icarus Verilog not installed")
@pytest.mark.parametrize("name", KERNELS)
def test_kernel_on_verilog_matches_reference(name):
    run = subprocess.run([sys.executable, ROOT / "tools" / "run.py", name], capture_output=True, text=True)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "PASS" in run.stdout
