TITLE = "Matrix multiply: C = A x B (4x4)"
GRID = 4
N = 4
A = [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16]]
B = [[1, 0, 0, 1], [0, 1, 0, 1], [0, 0, 1, 1], [2, 0, 0, -1]]


def setup():
    mem = {}
    for r in range(N):
        for c in range(N):
            mem[r * N + c] = A[r][c]
            mem[16 + r * N + c] = B[r][c]
    return mem


def check(mem):
    want = [[sum(A[r][k] * B[k][c] for k in range(N)) for c in range(N)] for r in range(N)]
    got = [mem[32 + r * N:32 + r * N + N] for r in range(N)]
    return got == want, "C =\n" + "\n".join(f"    {row}" for row in got)
