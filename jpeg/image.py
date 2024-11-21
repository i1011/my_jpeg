import numpy as np

def upsample_v(img: np.ndarray, k: int):
    ret = np.zeros((img.shape[0] * k, img.shape[1]), dtype=int)
    for i in range(k):
        ret[i::k, :] = img
    return ret

def upsample(img: np.ndarray, kv: int, kh: int):
    img = upsample_v(img, kv).T
    img = upsample_v(img, kh).T
    return img

def ycbcr2bgr(img: np.ndarray, shift):
    # https://www.w3.org/Graphics/JPEG/jfif3.pdf
    Y, Cb, Cr = img[0], img[1] - shift, img[2] - shift
    R = Y + 1.402 * Cr
    G = Y - 0.34414 * Cb - 0.71414 * Cr
    B = Y + 0.1772 * Cb
    return np.stack((B, G, R), axis=0)
