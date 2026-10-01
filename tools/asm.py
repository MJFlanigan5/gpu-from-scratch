"""Two-pass assembler for ForgeGPU assembly.

Syntax:
    # comment            (also ';')
    .equ NAME 123        named constant, usable anywhere an immediate is
    loop:                label (branch target)
    add  r3, r1, r2
    ld   r4, 16(r1)      memory operand: imm(rs)
    sreg r0, threadIdx
    bnz  r5, loop
"""

import re
import sys

from isa import IMM_MAX, IMM_MIN, NUM_REGS, OPCODES, SPECIAL_REGS, Instr


class AsmError(Exception):
    pass


def _reg(tok: str, line: int) -> int:
    m = re.fullmatch(r"r(\d+)", tok)
    if not m or int(m.group(1)) >= NUM_REGS:
        raise AsmError(f"line {line}: expected a register r0..r{NUM_REGS - 1}, got {tok!r}")
    return int(m.group(1))


def _imm(tok: str, symbols: dict[str, int], line: int) -> int:
    if tok in symbols:
        val = symbols[tok]
    else:
        try:
            val = int(tok, 0)
        except ValueError:
            raise AsmError(f"line {line}: unknown symbol or bad number {tok!r}") from None
    if not IMM_MIN <= val <= IMM_MAX:
        raise AsmError(f"line {line}: immediate {val} out of range")
    return val


def assemble(source: str) -> list[int]:
    # Pass 1: strip comments, collect labels and constants.
    symbols: dict[str, int] = {}
    statements: list[tuple[int, str, list[str]]] = []
    for lineno, raw in enumerate(source.splitlines(), 1):
        text = re.split(r"[#;]", raw, maxsplit=1)[0].strip()
        while (m := re.match(r"^([A-Za-z_]\w*):\s*", text)):
            symbols[m.group(1)] = len(statements)
            text = text[m.end():]
        if not text:
            continue
        if text.startswith(".equ"):
            parts = text.split()
            if len(parts) != 3:
                raise AsmError(f"line {lineno}: usage .equ NAME VALUE")
            symbols[parts[1]] = int(parts[2], 0)
            continue
        op, _, rest = text.partition(" ")
        args = [a.strip() for a in rest.split(",")] if rest.strip() else []
        statements.append((lineno, op.lower(), args))

    # Pass 2: encode.
    words = []
    for lineno, op, args in statements:
        if op not in OPCODES:
            raise AsmError(f"line {lineno}: unknown instruction {op!r}")
        fmt = OPCODES[op][1]
        expected = {"-": 0, "R": 3, "I": 3, "LI": 2, "MEM": 2, "SR": 2, "BR": 2}[fmt]
        if len(args) != expected:
            raise AsmError(f"line {lineno}: {op} takes {expected} operand(s), got {len(args)}")
        if fmt == "-":
            ins = Instr(op)
        elif fmt == "R":
            ins = Instr(op, _reg(args[0], lineno), _reg(args[1], lineno), _reg(args[2], lineno))
        elif fmt == "I":
            ins = Instr(op, _reg(args[0], lineno), _reg(args[1], lineno), imm=_imm(args[2], symbols, lineno))
        elif fmt == "LI":
            ins = Instr(op, _reg(args[0], lineno), imm=_imm(args[1], symbols, lineno))
        elif fmt == "MEM":
            m = re.fullmatch(r"(.*)\((r\d+)\)", args[1].replace(" ", ""))
            if not m:
                raise AsmError(f"line {lineno}: expected imm(rs), got {args[1]!r}")
            off = _imm(m.group(1) or "0", symbols, lineno)
            ins = Instr(op, _reg(args[0], lineno), _reg(m.group(2), lineno), imm=off)
        elif fmt == "SR":
            if args[1] not in SPECIAL_REGS:
                raise AsmError(f"line {lineno}: special register must be one of {list(SPECIAL_REGS)}")
            ins = Instr(op, _reg(args[0], lineno), imm=SPECIAL_REGS[args[1]])
        elif fmt == "BR":
            ins = Instr(op, rs=_reg(args[0], lineno), imm=_imm(args[1], symbols, lineno))
        words.append(ins.encode())
    return words


if __name__ == "__main__":
    for w in assemble(open(sys.argv[1]).read()):
        print(f"{w:08x}")
