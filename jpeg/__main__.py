import cv2 as cv

from jpeg import *
from jpeg.image import np, upsample
from jpeg.misc import DCT

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

def test_dct_idct_identity():
    dct = DCT()
    a = np.random.rand(8, 8)
    b = dct.idct(dct.dct(a))
    assert np.max(np.abs(a - b)) < 1e-9
    b = dct.dct(dct.idct(a))
    assert np.max(np.abs(a - b)) < 1e-9

test_upsample()
test_dct_idct_identity()
files = ["monalisa", "gig-sn01", "gig-sn08", "teatime"]
for file in files:
    img = JPEG().decode(open(f"Image/{file}.jpg", "rb"))
    cv.imwrite(f"Image/{file}.out.bmp", img)
