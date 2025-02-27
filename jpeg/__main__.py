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

def run_test():
    test_upsample()
    test_dct_idct_identity()
    files = ["monalisa", "gig-sn01", "gig-sn08", "teatime"]
    for file in files:
        img = JPEG().decode(open(f"Image/{file}.jpg", "rb"))
        cv.imwrite(f"Image/{file}.bmp", img)

        img2 = cv.imread(f"Image/{file}.jpg", cv.IMREAD_COLOR)
        cv.imwrite(f"Image/{file}-diff.png", cv.absdiff(img, img2))

import argparse
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--run-test", help="run tests", action="store_true")
    group.add_argument("file", help="input file", nargs='?')
    args = parser.parse_args()
    if args.run_test:
        run_test()
    elif not args.file:
        parser.print_help()
    else:
        file = str(args.file)
        img = JPEG().decode(open(file, "rb"))
        file = file.removesuffix('.jpg') + '.bmp'
        print(f"save to {file}")
        cv.imwrite(file, img)
