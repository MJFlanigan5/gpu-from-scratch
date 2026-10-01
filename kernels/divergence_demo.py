TITLE = "Branch divergence (expected to fail — see roadmap)"
GRID = 1
EXPECT_ERROR = True


def setup():
    return {}


def check(mem):
    return True, "core stopped with error=1, as expected"
