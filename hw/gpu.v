// ForgeGPU — a deliberately tiny SIMT GPU core.
//
// One core, NLANES threads ("lanes") that execute the SAME instruction in
// lockstep on DIFFERENT data. That is the whole trick behind GPU math: one
// instruction fetch/decode is shared by every lane, so adding lanes adds
// arithmetic throughput almost for free.
//
// A kernel is launched over `grid_dim` blocks; each block is NLANES threads.
// Blocks run one after another on this single core (a real GPU runs many
// blocks at once on many cores — see README roadmap).
//
// Pipeline (multi-cycle, not pipelined — easy to read in a waveform):
//   FETCH : read instruction at pc
//   EXEC  : every lane does the ALU op in parallel (1 cycle for all lanes)
//   MEM   : loads/stores go through ONE memory port, one lane per cycle.
//           This is the memory bottleneck real GPUs fight with wide,
//           coalesced memory buses and caches.
//
// Branches must be uniform: if lanes disagree on `bnz`, the core stops with
// `error` set (divergence). Real GPUs handle this with an execution mask and
// a reconvergence stack — a roadmap item.

`include "isa.vh"

module gpu #(
    parameter NLANES = 4,
    parameter PMEM_WORDS = 256,
    parameter DMEM_WORDS = 1024
) (
    input  wire       clk,
    input  wire       rst,
    input  wire       start,
    input  wire [7:0] grid_dim,
    output reg        done,
    output reg        error,
    output reg [31:0] cycles
);
    localparam S_IDLE = 3'd0, S_FETCH = 3'd1, S_EXEC = 3'd2, S_MEM = 3'd3, S_DONE = 3'd4;

    reg [31:0] pmem [0:PMEM_WORDS-1];          // program memory (loaded by testbench)
    reg [31:0] dmem [0:DMEM_WORDS-1];          // data memory, shared by all lanes
    reg signed [31:0] rf [0:NLANES*16-1];      // 16 registers per lane

    reg [2:0]  state;
    reg [7:0]  pc;
    reg [31:0] instr;
    reg [7:0]  block_idx;
    reg [7:0]  mlane;                          // which lane the MEM stage is serving

    wire [5:0]  op  = instr[31:26];
    wire [3:0]  rd  = instr[25:22];
    wire [3:0]  rs  = instr[21:18];
    wire [3:0]  rt  = instr[17:14];
    wire signed [31:0] imm = {{14{instr[17]}}, instr[17:0]};

    integer l, k;
    reg signed [31:0] a, b, res;
    reg any_true, all_true;
    reg [31:0] addr;

    always @(posedge clk) begin
        if (rst) begin
            state <= S_IDLE;
            done <= 0;
            error <= 0;
            cycles <= 0;
            pc <= 0;
            block_idx <= 0;
        end else begin
            if (state != S_IDLE && state != S_DONE) cycles <= cycles + 1;

            case (state)
            S_IDLE: if (start) begin
                for (k = 0; k < NLANES*16; k = k + 1) rf[k] <= 0;
                pc <= 0;
                block_idx <= 0;
                state <= (grid_dim == 0) ? S_DONE : S_FETCH;
                if (grid_dim == 0) done <= 1;
            end

            S_FETCH: begin
                instr <= pmem[pc];
                state <= S_EXEC;
            end

            S_EXEC: begin
`ifdef TRACE
                $display("T %0d EXEC blk=%0d pc=%0d instr=%08h", cycles, block_idx, pc, instr);
`endif
                pc <= pc + 1;
                state <= S_FETCH;
                case (op)
                `OP_NOP: ;
                `OP_HALT: begin
                    if (block_idx + 1 < grid_dim) begin
                        // next block: fresh registers, restart the program
                        block_idx <= block_idx + 1;
                        pc <= 0;
                        for (k = 0; k < NLANES*16; k = k + 1) rf[k] <= 0;
                    end else begin
                        done <= 1;
                        state <= S_DONE;
                    end
                end
                `OP_LD, `OP_ST: begin
                    mlane <= 0;
                    state <= S_MEM;
                end
                `OP_BNZ: begin
                    any_true = 0;
                    all_true = 1;
                    for (l = 0; l < NLANES; l = l + 1) begin
                        if (rf[l*16 + rs] != 0) any_true = 1;
                        else all_true = 0;
                    end
`ifdef TRACE
                    $display("T %0d BR taken=%0d divergent=%0d", cycles, all_true, any_true && !all_true);
`endif
                    if (any_true && !all_true) begin
                        error <= 1;          // divergence: lanes want different paths
                        done <= 1;
                        state <= S_DONE;
                    end else if (all_true) begin
                        pc <= imm[7:0];
                    end
                end
                default: begin
                    // ALU ops: every lane computes at once — this is the "parallel math".
                    for (l = 0; l < NLANES; l = l + 1) begin
                        a = rf[l*16 + rs];
                        b = rf[l*16 + rt];
                        case (op)
                        `OP_LI:   res = imm;
                        `OP_ADD:  res = a + b;
                        `OP_SUB:  res = a - b;
                        `OP_MUL:  res = a * b;
                        `OP_ADDI: res = a + imm;
                        `OP_SRA:  res = a >>> imm[4:0];
                        `OP_SLT:  res = (a < b) ? 1 : 0;
                        `OP_MAX:  res = (a > b) ? a : b;
                        `OP_SREG: case (imm[1:0])
                                    2'd0: res = l;
                                    2'd1: res = block_idx;
                                    2'd2: res = NLANES;
                                    default: res = grid_dim;
                                  endcase
                        default: begin
                            res = 0;
                            error <= 1;      // unknown opcode
                            done <= 1;
                            state <= S_DONE;
                        end
                        endcase
                        rf[l*16 + rd] <= res;
`ifdef TRACE
                        $display("T %0d WB lane=%0d rd=%0d val=%0d", cycles, l, rd, res);
`endif
                    end
                end
                endcase
            end

            S_MEM: begin
                addr = rf[mlane*16 + rs] + imm;
                if (addr >= DMEM_WORDS) begin
                    error <= 1;              // out-of-bounds access
                    done <= 1;
                    state <= S_DONE;
                end else if (op == `OP_LD) begin
                    rf[mlane*16 + rd] <= dmem[addr];
`ifdef TRACE
                    $display("T %0d LD lane=%0d rd=%0d addr=%0d val=%0d", cycles, mlane, rd, addr, $signed(dmem[addr]));
`endif
                end else begin
                    dmem[addr] <= rf[mlane*16 + rd];
`ifdef TRACE
                    $display("T %0d ST lane=%0d addr=%0d val=%0d", cycles, mlane, addr, rf[mlane*16 + rd]);
`endif
                end
                if (mlane + 1 == NLANES) state <= S_FETCH;
                else mlane <= mlane + 1;
            end

            S_DONE: ;
            default: state <= S_IDLE;
            endcase
        end
    end
endmodule
