# C[i] = A[i] + B[i]   — the "hello world" of GPU computing.
# One thread per element: 8 elements = 2 blocks x 4 lanes.
.equ A 0
.equ B 32
.equ C 64

    sreg r0, blockIdx
    sreg r1, blockDim
    sreg r2, threadIdx
    mul  r3, r0, r1        # i = blockIdx * blockDim + threadIdx
    add  r3, r3, r2        #   (every lane gets a different i — same code, different data)
    ld   r4, A(r3)
    ld   r5, B(r3)
    add  r6, r4, r5
    st   r6, C(r3)
    halt
