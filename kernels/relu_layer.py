TITLE = "Neural-network layer: y = ReLU(W.x + b) in Q8.8 fixed point"
GRID = 1
Q = 256  # Q8.8 scale
W = [[0.5, -1.0, 0.25, 2.0],
     [1.0, 1.0, 1.0, 1.0],
     [-2.0, 0.5, 0.0, -0.5],
     [0.75, 0.0, -1.5, 1.25]]
X = [1.0, 2.0, -0.5, 0.25]
BIAS = [0.1, -1.0, 0.0, 0.5]


def fx(v):
    return round(v * Q)


def setup():
    mem = {}
    for j in range(4):
        for k in range(4):
            mem[j * 4 + k] = fx(W[j][k])
    mem.update({16 + k: fx(v) for k, v in enumerate(X)})
    mem.update({20 + j: fx(v) for j, v in enumerate(BIAS)})
    return mem


def check(mem):
    # Bit-exact integer model of what the hardware does...
    want = []
    for j in range(4):
        acc = sum((fx(W[j][k]) * fx(X[k])) >> 8 for k in range(4)) + fx(BIAS[j])
        want.append(max(acc, 0))
    got = mem[24:28]
    # ...and the floating-point answer, to show the fixed-point error.
    exact = [max(sum(W[j][k] * X[k] for k in range(4)) + BIAS[j], 0.0) for j in range(4)]
    lines = [f"    y[{j}] = {g / Q:8.4f}   (float math: {e:8.4f})" for j, (g, e) in enumerate(zip(got, exact))]
    return got == want, "y =\n" + "\n".join(lines)
