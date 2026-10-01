// FPGA top level: a self-test you can flash onto a board.
//
// At power-up it copies a kernel (program + input data) from on-chip ROM into
// the GPU through the host port, runs it, reads the result region back and
// compares it with the expected answers. Then it lights an LED:
//   led_pass  — every result matched
//   led_fail  — a mismatch, or the core reported an error
//   led_busy  — still loading / running / checking
// The ROM images and sizes come from tools/fpga_image.py (build/fpga_*.hex,
// build/fpga_params.vh), so the same top level works for any kernel.
`include "fpga_params.vh"

module fpga_top (
    input  wire clk,
    output reg  led_pass,
    output reg  led_fail,
    output wire led_busy
);
    reg [31:0] prog_rom [0:`FPGA_NPROG-1];
    reg [31:0] data_rom [0:`FPGA_NDATA-1];
    reg [31:0] exp_rom  [0:`FPGA_NEXP-1];
    initial begin
        $readmemh("build/fpga_prog.hex", prog_rom);
        $readmemh("build/fpga_data.hex", data_rom);
        $readmemh("build/fpga_expect.hex", exp_rom);
    end

    // Power-on reset: hold reset for 16 cycles after configuration.
    reg [4:0] por = 0;
    wire rst = !por[4];
    always @(posedge clk) if (rst) por <= por + 1;

    localparam L_PROG = 3'd0, L_DATA = 3'd1, L_START = 3'd2, L_RUN = 3'd3,
               L_RADDR = 3'd4, L_RWAIT = 3'd7, L_RCHECK = 3'd5, L_DONE = 3'd6;
    reg [2:0]  st;
    reg [9:0]  i;
    reg        start, host_we, host_sel;
    reg [9:0]  host_addr;
    reg [31:0] host_wdata;
    wire [31:0] host_rdata;
    wire done, error;
    wire [31:0] cycles;
    reg  ok;

    gpu #(.NLANES(`FPGA_NLANES)) core (
        .clk(clk), .rst(rst), .start(start), .grid_dim(8'd`FPGA_GRID),
        .done(done), .error(error), .cycles(cycles),
        .host_we(host_we), .host_sel(host_sel), .host_addr(host_addr),
        .host_wdata(host_wdata), .host_rdata(host_rdata));

    assign led_busy = (st != L_DONE);

    always @(posedge clk) begin
        if (rst) begin
            st <= L_PROG; i <= 0; start <= 0; host_we <= 0; ok <= 1;
            led_pass <= 0; led_fail <= 0;
        end else begin
            host_we <= 0;
            start <= 0;
            case (st)
            L_PROG: begin
                host_we <= 1; host_sel <= 0; host_addr <= i; host_wdata <= prog_rom[i];
                if (i == `FPGA_NPROG - 1) begin i <= 0; st <= L_DATA; end else i <= i + 1;
            end
            L_DATA: begin
                host_we <= 1; host_sel <= 1; host_addr <= i; host_wdata <= data_rom[i];
                if (i == `FPGA_NDATA - 1) begin i <= 0; st <= L_START; end else i <= i + 1;
            end
            L_START: begin start <= 1; st <= L_RUN; end
            L_RUN: if (done) begin
                if (error) ok <= 0;
                st <= L_RADDR;
            end
            // host_addr is registered (reaches the RAM next cycle) and the RAM read
            // is synchronous (data the cycle after that): two cycles per read.
            L_RADDR: begin host_addr <= `FPGA_EXP_BASE + i; st <= L_RWAIT; end
            L_RWAIT: st <= L_RCHECK;
            L_RCHECK: begin
                if (host_rdata != exp_rom[i]) ok <= 0;
                if (i == `FPGA_NEXP - 1) st <= L_DONE;
                else begin i <= i + 1; st <= L_RADDR; end
            end
            L_DONE: begin led_pass <= ok; led_fail <= !ok; end
            default: st <= L_DONE;
            endcase
        end
    end
endmodule
