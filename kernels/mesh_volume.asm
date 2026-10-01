# Volume of a closed triangle mesh (the math FORGE's BOM needs), one
# triangle per thread. For triangle (v0, v1, v2) each thread computes
#     6 * signed volume of tetrahedron(origin, v0, v1, v2) = v0 . (v1 x v2)
# Summing every thread's result and dividing by 6 gives the solid's volume
# (divergence theorem). The final sum is done by the host for now — a
# parallel reduction on the GPU is on the roadmap.
.equ TRI 0      # 9 words per triangle: x0 y0 z0 x1 y1 z1 x2 y2 z2
.equ OUT 200

    sreg r0, blockIdx
    sreg r1, blockDim
    sreg r2, threadIdx
    mul  r3, r0, r1
    add  r3, r3, r2        # t = triangle index
    li   r4, 9
    mul  r4, r3, r4        # base = 9 * t
    ld   r5, 0(r4)         # x0
    ld   r6, 1(r4)         # y0
    ld   r7, 2(r4)         # z0
    ld   r8, 3(r4)         # x1
    ld   r9, 4(r4)         # y1
    ld   r10, 5(r4)        # z1
    ld   r11, 6(r4)        # x2
    ld   r12, 7(r4)        # y2
    ld   r13, 8(r4)        # z2
    mul  r0, r9, r13       # cx = y1*z2 - z1*y2
    mul  r1, r10, r12
    sub  r0, r0, r1
    mul  r0, r5, r0        # x0*cx
    mul  r1, r10, r11      # cy = z1*x2 - x1*z2
    mul  r2, r8, r13
    sub  r1, r1, r2
    mul  r1, r6, r1        # y0*cy
    add  r0, r0, r1
    mul  r1, r8, r12       # cz = x1*y2 - y1*x2
    mul  r2, r9, r11
    sub  r1, r1, r2
    mul  r1, r7, r1        # z0*cz
    add  r0, r0, r1        # 6 * signed volume
    st   r0, OUT(r3)
    halt
