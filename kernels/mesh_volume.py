TITLE = "Mesh volume (FORGE BOM math): 10 x 10 x 10 cube from 12 triangles"
GRID = 3
S = 10


def cube_triangles(s):
    """12 outward-wound triangles for an axis-aligned cube [0,s]^3."""
    v = [(x, y, z) for x in (0, s) for y in (0, s) for z in (0, s)]
    idx = lambda x, y, z: v.index((x * s, y * s, z * s))  # noqa: E731
    quads = [  # each quad counter-clockwise seen from outside
        (idx(0, 0, 0), idx(0, 1, 0), idx(1, 1, 0), idx(1, 0, 0)),  # bottom z=0
        (idx(0, 0, 1), idx(1, 0, 1), idx(1, 1, 1), idx(0, 1, 1)),  # top z=s
        (idx(0, 0, 0), idx(1, 0, 0), idx(1, 0, 1), idx(0, 0, 1)),  # front y=0
        (idx(0, 1, 0), idx(0, 1, 1), idx(1, 1, 1), idx(1, 1, 0)),  # back y=s
        (idx(0, 0, 0), idx(0, 0, 1), idx(0, 1, 1), idx(0, 1, 0)),  # left x=0
        (idx(1, 0, 0), idx(1, 1, 0), idx(1, 1, 1), idx(1, 0, 1)),  # right x=s
    ]
    tris = []
    for a, b, c, d in quads:
        tris += [(v[a], v[b], v[c]), (v[a], v[c], v[d])]
    return tris


TRIS = cube_triangles(S)


def setup():
    mem = {}
    for t, tri in enumerate(TRIS):
        for i, val in enumerate(c for vert in tri for c in vert):
            mem[9 * t + i] = val
    return mem


def check(mem):
    parts = mem[200:200 + len(TRIS)]
    volume = sum(parts) / 6
    return volume == S ** 3, f"per-triangle 6V = {parts}\n    volume = sum / 6 = {volume:g}  (expected {S ** 3})"
