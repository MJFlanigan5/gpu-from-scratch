// Simulates the FPGA self-test exactly as it would run on a board.
`timescale 1ns/1ns
module tb_fpga;
    reg clk = 0;
    wire pass, fail, busy;
    fpga_top dut (.clk(clk), .led_pass(pass), .led_fail(fail), .led_busy(busy));
    always #5 clk = ~clk;
    integer i;
    initial begin
        repeat (40) @(posedge clk);                  // let power-on reset finish
        for (i = 0; i < 200000 && busy; i = i + 1) @(posedge clk);
        @(posedge clk); @(posedge clk);
        $display("LEDS pass=%0d fail=%0d busy=%0d cycles=%0d", pass, fail, busy, dut.cycles);
        $finish;
    end
endmodule
