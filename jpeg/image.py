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
