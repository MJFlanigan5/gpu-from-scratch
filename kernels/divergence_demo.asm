# What happens when lanes disagree on a branch?
# Lane 0 has threadIdx == 0, the others don't — so `bnz` wants to send lanes
# down different paths. This GPU has no execution mask yet, so it stops with
# an error. (Real GPUs run both paths with some lanes switched off.)
    sreg r0, threadIdx
    bnz  r0, skip
    li   r1, 111
skip:
    halt
