// Exercises the host port the way an FPGA board's UART bridge would:
// write the program and an input value through host_*, run, read back.
`timescale 1ns/1ns
module tb_host;
    reg clk = 0, rst = 1, start = 0;
    reg host_we = 0, host_sel = 0;
    reg [9:0] host_addr = 0;
    reg [31:0] host_wdata = 0;
    wire [31:0] host_rdata;
    wire done, error;
    wire [31:0] cycles;
    reg [31:0] prog [0:15];
    reg [1023:0] prog_file;
    integer i;

    gpu #(.NLANES(4)) dut (.clk(clk), .rst(rst), .start(start), .grid_dim(8'd1),
        .done(done), .error(error), .cycles(cycles),
        .host_we(host_we), .host_sel(host_sel), .host_addr(host_addr),
        .host_wdata(host_wdata), .host_rdata(host_rdata));
    always #5 clk = ~clk;

    task host_write(input sel, input [9:0] a, input [31:0] d);
        begin
            @(negedge clk); host_we = 1; host_sel = sel; host_addr = a; host_wdata = d;
            @(negedge clk); host_we = 0;
        end
    endtask

    initial begin
        if (!$value$plusargs("prog=%s", prog_file)) $fatal(1, "missing +prog=");
        for (i = 0; i < 16; i = i + 1) prog[i] = 32'h04000000;
        $readmemh(prog_file, prog);
        @(negedge clk); rst = 0;
        for (i = 0; i < 16; i = i + 1) host_write(0, i, prog[i]);
        host_write(1, 100, 32'd7);                   // input value
        @(negedge clk); start = 1; @(negedge clk); start = 0;
        for (i = 0; i < 1000 && !done; i = i + 1) @(posedge clk);
        for (i = 0; i < 4; i = i + 1) begin
            @(negedge clk); host_addr = 200 + i;
            @(negedge clk);                            // synchronous read: data next cycle
            $display("READ %0d %0d", 200 + i, host_rdata);
        end
        $display("RESULT done=%0d error=%0d", done, error);
        $finish;
    end
endmodule
