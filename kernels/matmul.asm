# C = A x B for 4x4 integer matrices (row-major).
# One thread per output element: block = row, lane = column -> grid of 4 blocks.
# Every lane runs the same k-loop, so the branch is uniform (no divergence).
.equ A 0
.equ B 16
.equ C 32
.equ N 4

    sreg r0, blockIdx      # row
    sreg r1, threadIdx     # col
    li   r2, 0             # k
    li   r3, 0             # acc
    li   r10, N
    mul  r4, r0, r10       # row * N
loop:
    add  r5, r4, r2        # A[row][k]
    ld   r6, A(r5)
    mul  r7, r2, r10       # B[k][col]
    add  r7, r7, r1
    ld   r8, B(r7)
    mul  r9, r6, r8        # multiply ...
    add  r3, r3, r9        # ... accumulate  (a real GPU fuses these: FMA)
    addi r2, r2, 1
    slt  r11, r2, r10      # k < N ?
    bnz  r11, loop
    add  r12, r4, r1
    st   r3, C(r12)
    halt
