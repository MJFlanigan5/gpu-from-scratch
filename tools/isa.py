"""The ForgeGPU instruction set — single source of truth for the assembler,
the reference model and the disassembler. hw/isa.vh must match OPCODES
(tests/test_isa_sync.py checks this).

Every instruction is 32 bits:

    31      26 25  22 21  18 17  14 13           0
    +---------+------+------+------+--------------+
    | opcode  |  rd  |  rs  |  rt  |   (unused)   |   R-type
    +---------+------+------+------+--------------+
    | opcode  |  rd  |  rs  |      imm18 (signed) |   I-type
    +---------+------+------+---------------------+

There are 16 general registers per thread (r0..r15), each 32-bit signed.
"""

from dataclasses import dataclass

# name -> (opcode, operand format)
#   R   : rd, rs, rt
#   I   : rd, rs, imm
#   LI  : rd, imm
#   MEM : rd, imm(rs)
#   SR  : rd, special-register name
#   BR  : rs, label
#   -   : no operands
OPCODES: dict[str, tuple[int, str]] = {
    "nop":  (0x00, "-"),
    "halt": (0x01, "-"),
    "li":   (0x02, "LI"),   # rd = imm
    "add":  (0x03, "R"),    # rd = rs + rt
    "sub":  (0x04, "R"),    # rd = rs - rt
    "mul":  (0x05, "R"),    # rd = low 32 bits of rs * rt
    "addi": (0x06, "I"),    # rd = rs + imm
    "sra":  (0x07, "I"),    # rd = rs >>> imm   (arithmetic: keeps sign; used for fixed-point)
    "ld":   (0x08, "MEM"),  # rd = mem[rs + imm]
    "st":   (0x09, "MEM"),  # mem[rs + imm] = rd
    "sreg": (0x0A, "SR"),   # rd = special register
    "slt":  (0x0B, "R"),    # rd = (rs < rt) ? 1 : 0
    "bnz":  (0x0C, "BR"),   # if rs != 0 goto label   (must be uniform across the block)
    "max":  (0x0D, "R"),    # rd = max(rs, rt)        (ReLU is `max rd, rs, rZERO`)
}

SPECIAL_REGS = {"threadIdx": 0, "blockIdx": 1, "blockDim": 2, "gridDim": 3}

NUM_REGS = 16
IMM_BITS = 18
IMM_MIN, IMM_MAX = -(1 << (IMM_BITS - 1)), (1 << (IMM_BITS - 1)) - 1
MASK32 = 0xFFFF_FFFF

BY_OPCODE = {code: (name, fmt) for name, (code, fmt) in OPCODES.items()}


def to_signed32(v: int) -> int:
    v &= MASK32
    return v - (1 << 32) if v & 0x8000_0000 else v


@dataclass(frozen=True)
class Instr:
    op: str
    rd: int = 0
    rs: int = 0
    rt: int = 0
    imm: int = 0

    def encode(self) -> int:
        code, fmt = OPCODES[self.op]
        word = (code << 26) | (self.rd << 22) | (self.rs << 18)
        if fmt == "R":
            word |= self.rt << 14
        elif fmt in ("I", "LI", "MEM", "SR", "BR"):
            if not IMM_MIN <= self.imm <= IMM_MAX:
                raise ValueError(f"immediate {self.imm} out of range for {self.op}")
            word |= self.imm & ((1 << IMM_BITS) - 1)
        return word


def decode(word: int) -> Instr:
    code = (word >> 26) & 0x3F
    if code not in BY_OPCODE:
        raise ValueError(f"unknown opcode 0x{code:02x} in word 0x{word:08x}")
    name, _ = BY_OPCODE[code]
    imm = word & ((1 << IMM_BITS) - 1)
    if imm & (1 << (IMM_BITS - 1)):
        imm -= 1 << IMM_BITS
    return Instr(name, (word >> 22) & 0xF, (word >> 18) & 0xF, (word >> 14) & 0xF, imm)


def disasm(word: int) -> str:
    i = decode(word)
    fmt = OPCODES[i.op][1]
    if fmt == "-":
        return i.op
    if fmt == "R":
        return f"{i.op} r{i.rd}, r{i.rs}, r{i.rt}"
    if fmt == "I":
        return f"{i.op} r{i.rd}, r{i.rs}, {i.imm}"
    if fmt == "LI":
        return f"{i.op} r{i.rd}, {i.imm}"
    if fmt == "MEM":
        return f"{i.op} r{i.rd}, {i.imm}(r{i.rs})"
    if fmt == "SR":
        names = {v: k for k, v in SPECIAL_REGS.items()}
        return f"{i.op} r{i.rd}, {names.get(i.imm, i.imm)}"
    if fmt == "BR":
        return f"{i.op} r{i.rs}, {i.imm}"
    raise AssertionError(fmt)
