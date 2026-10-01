TITLE = "Vector add: C[i] = A[i] + B[i]"
GRID = 2
A = [1, 2, 3, 4, 5, 6, 7, 8]
B = [10, 20, 30, 40, 50, 60, 70, 80]


def setup():
    mem = {i: v for i, v in enumerate(A)}
    mem.update({32 + i: v for i, v in enumerate(B)})
    return mem


def check(mem):
    got = mem[64:72]
    want = [a + b for a, b in zip(A, B)]
    return got == want, f"C = {got}  (expected {want})"
