import numpy as np

from .debug import debug
class BitStream:
    def __init__(self, data: bytes):
        self.data = data
        self.offset = 0

    def tell(self):
        return self.offset

    def seek(self, offset: int, whence=0):
        if whence == 1:
            self.offset += offset
        else:
            self.offset = offset

    def read(self):
        if self.offset // 8 >= len(self.data):
            return 0
        val = self.data[self.offset // 8]
        val >>= 7 - self.offset % 8
        val %= 2
        self.offset += 1
        return val
    
    def read_n(self, n: int):
        assert n >= 0
        ret = 0
        for _ in range(n): ret = ret * 2 + self.read()
        return ret

    def read_signed(self, n: int):
        if n <= 0: return 0
        ret = self.read_n(n)
        if ret >> (n - 1) == 0:
            ret -= 2 ** n - 1
        return ret

class HuffmanTable:
    def insert_sym(self, code: str, sym: int):
        cur = self.nodes[0]
        for c in code:
            if c == '0': t = 0
            else: t = 1
            if cur[t] is None:
                self.nodes.append([None, None, None])
                cur[t] = self.nodes[-1]
            cur = cur[t]
        cur[2] = sym
        
    def __init__(self, ht):
        debug('Init HT')
        debug(ht)
        debug('Count:', sum(len(x) for x in ht))
        self.nodes = [[None, None, None]] # [child-0, child-1, symbol]
        acc = 0
        for L in range(16):
            acc *= 2 # append 0
            self.nodes.append([0, 0, 0])
            for x in ht[L]:
                debug(f'{acc:0{L + 1}b}', x)
                self.insert_sym(f'{acc:0{L + 1}b}', x)
                acc += 1
        debug()

    def next(self, stream: BitStream):
        cur = self.nodes[0]
        while cur[2] is None:
            cur = cur[stream.read()]
        return cur[2]

def ziglag(a: np.ndarray):
    pos = np.array([
        0, 1, 5, 6, 14, 15, 27, 28,
        2, 4, 7, 13, 16, 26, 29, 42,
        3, 8, 12, 17, 25, 30, 41, 43,
        9, 11, 18, 24, 31, 40, 44, 53,
        10, 19, 23, 32, 39, 45, 52, 54,
        20, 22, 33, 38, 46, 51, 55, 60,
        21, 34, 37, 47, 50, 56, 59, 61,
        35, 36, 48, 49, 57, 58, 62, 63,
    ])
    return a[pos].reshape(8, 8)