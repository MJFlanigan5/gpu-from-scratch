"""Reference model: executes ForgeGPU programs in Python with the same
semantics AND the same cycle accounting as hw/gpu.v.

It emits the same event stream as the Verilog TRACE output, so tools/run.py
can check the hardware against it event-for-event, not just by final memory.
Readable on purpose — if you want to understand what the hardware does,
read this file next to hw/gpu.v.
"""

from dataclasses import dataclass, field

from isa import MASK32, decode, to_signed32

DMEM_WORDS = 1024


@dataclass
class Result:
    mem: list[int]
    events: list[tuple]
    cycles: int
    error: bool
    instructions: int = 0
    lane_ops: int = 0          # ALU operations actually performed (instructions x lanes)
    mem_cycles: int = 0        # cycles spent waiting on the single memory port
    notes: list[str] = field(default_factory=list)


def run(program: list[int], mem: list[int], grid: int, lanes: int = 4, max_cycles: int = 200_000) -> Result:
    mem = [to_signed32(v) for v in mem] + [0] * (DMEM_WORDS - len(mem))
    events: list[tuple] = []
    cycles = instructions = lane_ops = mem_cycles = 0
    error = False

    for block in range(grid):
        regs = [[0] * 16 for _ in range(lanes)]
        pc = 0
        while True:
            if cycles > max_cycles:
                return Result(mem, events, cycles, True, instructions, lane_ops, mem_cycles, ["timeout"])
            word = program[pc] if pc < len(program) else 0x0400_0000  # HALT past the end
            ins = decode(word)
            cycles += 1                                     # FETCH
            events.append(("EXEC", block, pc, word))
            cycles += 1                                     # EXEC
            instructions += 1
            next_pc = pc + 1

            if ins.op == "nop":
                pass
            elif ins.op == "halt":
                break
            elif ins.op in ("ld", "st"):
                for lane in range(lanes):
                    # One lane at a time through the single memory port, 2 cycles each:
                    # issue the address, then the synchronous RAM returns data.
                    cycles += 1
                    mem_cycles += 1
                    addr = (regs[lane][ins.rs] + ins.imm) & MASK32
                    if addr >= DMEM_WORDS:
                        return Result(mem, events, cycles, True, instructions, lane_ops, mem_cycles,
                                      [f"out-of-bounds address {addr} (block {block}, lane {lane}, pc {pc})"])
                    if ins.op == "ld":
                        regs[lane][ins.rd] = mem[addr]
                        events.append(("LD", lane, ins.rd, addr, mem[addr]))
                    else:
                        mem[addr] = regs[lane][ins.rd]
                        events.append(("ST", lane, addr, regs[lane][ins.rd]))
                    cycles += 1
                    mem_cycles += 1
            elif ins.op == "bnz":
                takes = [regs[lane][ins.rs] != 0 for lane in range(lanes)]
                divergent = any(takes) and not all(takes)
                events.append(("BR", int(all(takes)), int(divergent)))
                if divergent:
                    return Result(mem, events, cycles, True, instructions, lane_ops, mem_cycles,
                                  [f"branch divergence at pc {pc} (block {block}): lanes {takes}"])
                if all(takes):
                    next_pc = ins.imm & 0xFF
            else:
                for lane in range(lanes):
                    a, b = regs[lane][ins.rs], regs[lane][ins.rt]
                    res = {
                        "li":   lambda: ins.imm,
                        "add":  lambda: a + b,
                        "sub":  lambda: a - b,
                        "mul":  lambda: a * b,
                        "addi": lambda: a + ins.imm,
                        "sra":  lambda: a >> (ins.imm & 31),
                        "slt":  lambda: int(a < b),
                        "max":  lambda: max(a, b),
                        "sreg": lambda: [lane, block, lanes, grid][ins.imm & 3],
                    }[ins.op]()
                    res = to_signed32(res)
                    regs[lane][ins.rd] = res
                    events.append(("WB", lane, ins.rd, res))
                    lane_ops += 1
            pc = next_pc

    return Result(mem, events, cycles, error, instructions, lane_ops, mem_cycles)
