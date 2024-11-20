import numpy as np

import math

from collections import namedtuple
from io import BytesIO
from struct import unpack
from typing import BinaryIO

from .image import upsample

class JPEGDecodeError(ValueError):
    def __init__(self, msg, data, pos):
        errmsg = '%s: index %d' % (msg, pos)
        ValueError.__init__(self, errmsg)
        self.msg = msg
        self.data = data
        self.pos = pos

MARKERS = {
    'SOI': b'\xff\xd8',
    'APP0': b'\xff\xe0',
    'DQT': b'\xff\xdb',
    'SOF0': b'\xff\xc0', # Baseline DCT
    'DHT': b'\xff\xc4',
    'SOS': b'\xff\xda',
    'EOI': b'\xff\xd9',
    'COM': b'\xff\xfe',
}

MARKERS_MAP = {
    MARKERS[k]: k for k in MARKERS
}

DEBUG = True
def debug(*args, **kwargs):
    if not DEBUG: return
    print(*args, **kwargs)

def unpack_int4(b: bytes):
    return divmod(unpack('B', b)[0], 0x10)

def ensure_range(data: BinaryIO, varname: str, value: int, min_value: int, max_value: int):
    if min_value <= value <= max_value: return
    raise JPEGDecodeError(f"Expecting {varname} in the range [{min_value}, {max_value}] but was {value}", data, data.tell())

def ensure_set(data: BinaryIO, varname: str, value: int, st: list):
    if value in st: return
    raise JPEGDecodeError(f"Expecting {varname} in the set {st} but was {value}", data, data.tell())

def ensure_eos(data: BinaryIO):
    b = data.read(1)
    if not b: return
    raise JPEGDecodeError(f"Expecting end of segment but 0x{b.hex()} was found", data, data.tell())

class JPEG:
    def __init__(self):
        self.qts = {}
        self.dcs = {}
        self.acs = {}
        self.csp = {}
        self.Y = self.X = -1
        self.scan = []

    def dqt(self, segment: bytes):
        # B.2.4.1 Quantization table-specification syntax
        data = BytesIO(segment)
        while True:
            PqTq = data.read(1)
            if not PqTq: break
            Pq, Tq = unpack_int4(PqTq)
            if Pq != 0: raise JPEGDecodeError(f"Unknown Pq {Pq}", data, data.tell())
            Q = unpack('B' * 64, data.read(64))
            self.qts[Tq] = Q
        ensure_eos(data)

    def sof0(self, segment: bytes):
        # B.2.2 Frame header syntax
        data = BytesIO(segment)
        P, Y, X, Nf = unpack('>BHHB', data.read(6))
        if Nf != 3: raise JPEGDecodeError(f"Expecting YCbCr mode but Nf = {Nf}", data, data.tell())
        for _ in range(Nf):
            C, HV, Tq = unpack('BBB', data.read(3))
            H, V = divmod(HV, 0x10)
            ensure_set(data, 'H', H, [1, 2, 4])
            ensure_set(data, 'V', V, [1, 2, 4])
            self.csp[C] = {'H': H, 'V': V, 'Tq': Tq}
        self.Y, self.X = Y, X
        ensure_eos(data)

    def dht(self, segment: bytes):
        # B.2.4.2 Huffman table-specification syntax
        data = BytesIO(segment)
        while True:
            TcTh = data.read(1)
            if not TcTh: break
            Tc, Th = unpack_int4(TcTh)
            ensure_range(data, 'Tc', Tc, 0, 1)
            L = unpack('B' * 16, data.read(16))
            V = [unpack('B' * L[i], data.read(L[i])) for i in range(16)]
            if Tc == 0: self.dcs[Th] = V
            else: self.acs[Th] = V
        ensure_eos(data)

    def sos(self, segment: bytes):
        # B.2.3 Scan header syntax
        data = BytesIO(segment)
        Ns = unpack('B', data.read(1))[0]
        for _ in range(Ns):
            Cs, TdTa = unpack('BB', data.read(2))
            Td, Ta = divmod(TdTa, 0x10)
            self.scan.append({'Cs': Cs, 'Td': Td, 'Ta': Ta})
        data.read(3) # Ss, Se, Ah, Al
        ensure_eos(data)

    def decode_ecs(self, segment: bytes):
        debug('QT:', self.qts)
        debug('DC:', self.dcs)
        debug('AC:', self.acs)
        debug('CSP:', self.csp)
        debug('Y X:', self.Y, self.X)
        debug('scan:', self.scan)
        debug(len(segment))

        # A.1.1 Dimensions and sampling factors
        Vmax = max(x['V'] for x in self.csp.values())
        Hmax = max(x['H'] for x in self.csp.values())
        # A.2.4 Completion of partial MCU
        MCU_Y, MCU_X = 8 * Vmax, 8 * Hmax
        Y = math.ceil(self.Y / MCU_Y) * MCU_Y
        X = math.ceil(self.X / MCU_X) * MCU_X
        #
        ScanParam = namedtuple('ScanParam', ['Cs', 'H', 'V', 'qt', 'dc', 'ac'])
        scan: list[ScanParam] = []
        for a in self.scan:
            b = self.csp[a['Cs']]
            scan.append(ScanParam(
                a['Cs'], b['H'], b['V'],
                self.qts[b['Tq']], self.dcs[a['Td']], self.acs[a['Ta']]
            ))

        img = np.zeros((3, Y, X), dtype=int)
        def parse_block(param: ScanParam):
            return np.zeros((8, 8), dtype=int)

        def parse_mcu():
            mcu = np.zeros((3, MCU_Y, MCU_X), dtype=int)
            for param in scan:
                buf = np.zeros((8 * param.V, 8 * param.H), dtype=int)
                for i in range(param.V):
                    for j in range(param.H):
                        buf[8 * i: 8 * i + 8, 8 * j: 8 * j + 8] = parse_block(param)
                mcu[param.Cs - 1] = upsample(buf, Vmax // param.V, Hmax // param.H)
            return mcu

        for i in range(0, Y, MCU_Y):
            for j in range(0, X, MCU_X):
                img[:, i: i + MCU_Y, j: j + MCU_X] = parse_mcu()

    def decode(self, data: BinaryIO):
        def __read_int16():
            return unpack('>H', data.read(2))[0]

        def __expect_bytes(p: bytes):
            q = data.read(len(p))
            if q != p:
                raise JPEGDecodeError(f"Expecting value 0x{p.hex()} but was 0x{q.hex()}", data, data.tell())

        __expect_bytes(MARKERS['SOI'])
        while True:
            marker = data.read(2)
            if marker not in MARKERS_MAP:
                raise JPEGDecodeError(f"Unexpected marker 0x{marker.hex()}", data, data.tell())
            marker = MARKERS_MAP[marker]
            if marker == 'SOI':
                raise JPEGDecodeError(f"Unexpected marker {marker}", data, data.tell())
            if marker == 'EOI':
                break
            L = __read_int16()
            segment = data.read(L - 2)

            if marker == 'APP0' or marker == 'COM':
                continue
            if marker == 'DQT':
                self.dqt(segment)
            elif marker == 'SOF0':
                self.sof0(segment)
            elif marker == 'DHT':
                self.dht(segment)
            elif marker == 'SOS':
                self.sos(segment)
                segment = []
                while True:
                    val = data.read(1)
                    if val == b'\xff': val += data.read(1)
                    if val == b'\xff\x00': val = b'\xff'
                    if len(val) == 2: # marker
                        data.seek(-2, 1)
                        break
                    segment.append(val)
                self.decode_ecs(b''.join(segment))
        ensure_eos(data)
