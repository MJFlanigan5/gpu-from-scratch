// Opcodes — must match tools/isa.py (checked by tests/test_isa_sync.py).
`define OP_NOP  6'h00
`define OP_HALT 6'h01
`define OP_LI   6'h02
`define OP_ADD  6'h03
`define OP_SUB  6'h04
`define OP_MUL  6'h05
`define OP_ADDI 6'h06
`define OP_SRA  6'h07
`define OP_LD   6'h08
`define OP_ST   6'h09
`define OP_SREG 6'h0A
`define OP_SLT  6'h0B
`define OP_BNZ  6'h0C
`define OP_MAX  6'h0D
