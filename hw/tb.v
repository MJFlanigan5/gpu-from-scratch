// Testbench: load a program + data image, launch the kernel, dump memory.
//
//   vvp sim.vvp +prog=build/prog.hex +data=build/data.hex +out=build/out.hex +grid=2
`timescale 1ns/1ns

module tb;
    reg clk = 0, rst = 1, start = 0;
    reg [7:0] grid;
    wire done, error;
    wire [31:0] cycles;
    reg [1023:0] prog_file, data_file, out_file;
    integer i, timeout;

    gpu #(.NLANES(`NLANES)) dut (
        .clk(clk), .rst(rst), .start(start), .grid_dim(grid),
        .done(done), .error(error), .cycles(cycles),
        .host_we(1'b0), .host_sel(1'b0), .host_addr(10'd0), .host_wdata(32'd0), .host_rdata()
    );

    always #5 clk = ~clk;

    initial begin
        if (!$value$plusargs("prog=%s", prog_file)) $fatal(1, "missing +prog=");
        if (!$value$plusargs("data=%s", data_file)) $fatal(1, "missing +data=");
        if (!$value$plusargs("out=%s", out_file))   $fatal(1, "missing +out=");
        if (!$value$plusargs("grid=%d", grid))      grid = 1;
        if (!$value$plusargs("timeout=%d", timeout)) timeout = 200000;

        for (i = 0; i < 256; i = i + 1)  dut.pmem[i] = 32'h04000000;  // fill with HALT
        for (i = 0; i < 1024; i = i + 1) dut.dmem[i] = 0;
        $readmemh(prog_file, dut.pmem);
        $readmemh(data_file, dut.dmem);

        @(posedge clk); @(posedge clk);
        rst = 0;
        @(posedge clk);
        start = 1;
        @(posedge clk);
        start = 0;

        for (i = 0; i < timeout && !done; i = i + 1) @(posedge clk);
        @(posedge clk);

        $writememh(out_file, dut.dmem);
        $display("RESULT done=%0d error=%0d cycles=%0d lanes=%0d", done, error, cycles, `NLANES);
        $finish;
    end
endmodule
