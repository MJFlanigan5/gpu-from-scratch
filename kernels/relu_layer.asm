# One neural-network layer: y = ReLU(W . x + b), in Q8.8 fixed point.
# Q8.8 means "integer / 256": 1.5 is stored as 384. Multiplying two Q8.8
# numbers gives Q16.16, so we shift right by 8 to get back to Q8.8.
# Lane j computes output neuron j. All lanes read the same x[k] (a broadcast).
.equ W 0       # 4x4 weights, row-major (row = output neuron)
.equ X 16      # 4 inputs
.equ BIAS 20   # 4 biases
.equ Y 24      # 4 outputs
.equ N 4

    sreg r0, threadIdx     # j
    li   r1, 0             # k
    li   r2, 0             # acc
    li   r10, N
    mul  r3, r0, r10       # j * N
loop:
    add  r4, r3, r1
    ld   r5, W(r4)         # W[j][k]
    ld   r6, X(r1)         # x[k]  (same address in every lane)
    mul  r7, r5, r6        # Q8.8 * Q8.8 = Q16.16
    sra  r7, r7, 8         # back to Q8.8
    add  r2, r2, r7
    addi r1, r1, 1
    slt  r11, r1, r10
    bnz  r11, loop
    ld   r8, BIAS(r0)
    add  r2, r2, r8
    li   r12, 0
    max  r2, r2, r12       # ReLU: negative -> 0
    st   r2, Y(r0)
    halt
