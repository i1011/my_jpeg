from jpeg import *
from jpeg.image import np, upsample

def test_upsample():
    a = np.array([
        [1, 2],
        [3, 4]
    ])
    b = np.array([
        [1, 1, 1, 2, 2, 2],
        [1, 1, 1, 2, 2, 2],
        [3, 3, 3, 4, 4, 4],
        [3, 3, 3, 4, 4, 4],
    ])
    assert np.array_equal(upsample(a, 2, 3), b)

test_upsample()
files = ["monalisa", "gig-sn01", "gig-sn08", "teatime"]
for file in files:
    JPEG().decode(open(f"Image/{file}.jpg", "rb"))
    break
