import numpy as np

import math

from dataclasses import dataclass
from io import BytesIO
from struct import unpack
from typing import BinaryIO

from .debug import debug
from .misc import *
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

def unpack_int4(b: bytes):
    return divmod(unpack('B', b)[0], 0x10)

def ensure_range(stream: BinaryIO, varname: str, value: int, min_value: int, max_value: int):
    if min_value <= value <= max_value: return
    raise JPEGDecodeError(f"Expecting {varname} in the range [{min_value}, {max_value}] but was {value}", stream, stream.tell())

def ensure_set(stream: BinaryIO, varname: str, value: int, st: list):
    if value in st: return
    raise JPEGDecodeError(f"Expecting {varname} in the set {st} but was {value}", stream, stream.tell())

def ensure_eos(stream: BinaryIO):
    b = stream.read(1)
    if not b: return
    raise JPEGDecodeError(f"Expecting end of segment but 0x{b.hex()} was found", stream, stream.tell())

@dataclass
class ScanParam():
    Cs: int
    H: int
    V: int
    qt: list[int]
    dc: HuffmanTable
    ac: HuffmanTable
    dc_acc: int = 0

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
        stream = BytesIO(segment)
        while True:
            PqTq = stream.read(1)
            if not PqTq: break
            Pq, Tq = unpack_int4(PqTq)
            if Pq != 0: raise JPEGDecodeError(f"Unknown Pq {Pq}", stream, stream.tell())
            Q = unpack('B' * 64, stream.read(64))
            self.qts[Tq] = Q
        ensure_eos(stream)

    def sof0(self, segment: bytes):
        # B.2.2 Frame header syntax
        stream = BytesIO(segment)
        P, Y, X, Nf = unpack('>BHHB', stream.read(6))
        if Nf != 3: raise JPEGDecodeError(f"Expecting YCbCr mode but Nf = {Nf}", stream, stream.tell())
        for _ in range(Nf):
            C, HV, Tq = unpack('BBB', stream.read(3))
            H, V = divmod(HV, 0x10)
            ensure_set(stream, 'H', H, [1, 2, 4])
            ensure_set(stream, 'V', V, [1, 2, 4])
            self.csp[C] = {'H': H, 'V': V, 'Tq': Tq}
        self.Y, self.X = Y, X
        ensure_eos(stream)

    def dht(self, segment: bytes):
        # B.2.4.2 Huffman table-specification syntax
        stream = BytesIO(segment)
        while True:
            TcTh = stream.read(1)
            if not TcTh: break
            Tc, Th = unpack_int4(TcTh)
            ensure_range(stream, 'Tc', Tc, 0, 1)
            L = unpack('B' * 16, stream.read(16))
            V = [unpack('B' * L[i], stream.read(L[i])) for i in range(16)]
            if Tc == 0: self.dcs[Th] = HuffmanTable(V)
            else: self.acs[Th] = HuffmanTable(V)
        ensure_eos(stream)

    def sos(self, segment: bytes):
        # B.2.3 Scan header syntax
        stream = BytesIO(segment)
        Ns = unpack('B', stream.read(1))[0]
        for _ in range(Ns):
            Cs, TdTa = unpack('BB', stream.read(2))
            Td, Ta = divmod(TdTa, 0x10)
            self.scan.append({'Cs': Cs, 'Td': Td, 'Ta': Ta})
        stream.read(3) # Ss, Se, Ah, Al
        ensure_eos(stream)

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
        scan: list[ScanParam] = []
        for a in self.scan:
            b = self.csp[a['Cs']]
            scan.append(ScanParam(
                a['Cs'], b['H'], b['V'],
                self.qts[b['Tq']], self.dcs[a['Td']], self.acs[a['Ta']]
            ))

        stream = BitStream(segment)
        img = np.zeros((3, Y, X), dtype=int)

        def decode_block(param: ScanParam):
            a = np.zeros((8, 8), dtype=float)

            # Differential DC encoding
            T = scan[0].dc.next(stream)
            diff = stream.read_n(T)
            if diff >> (T - 1) == 0:
                diff -= 2 ** T - 1
            param.dc_acc += diff
            a[0, 0] = param.dc_acc

            # Run-length encoding

            debug(a)
            exit(0)
            return np.zeros((8, 8), dtype=int)

        def decode_mcu():
            mcu = np.zeros((3, MCU_Y, MCU_X), dtype=int)
            for param in scan:
                buf = np.zeros((8 * param.V, 8 * param.H), dtype=int)
                for i in range(param.V):
                    for j in range(param.H):
                        buf[8 * i: 8 * i + 8, 8 * j: 8 * j + 8] = decode_block(param)
                mcu[param.Cs - 1] = upsample(buf, Vmax // param.V, Hmax // param.H)
            return mcu

        for i in range(0, Y, MCU_Y):
            for j in range(0, X, MCU_X):
                img[:, i: i + MCU_Y, j: j + MCU_X] = decode_mcu()

    def decode(self, stream: BinaryIO):
        def __read_int16():
            return unpack('>H', stream.read(2))[0]

        def __expect_bytes(p: bytes):
            q = stream.read(len(p))
            if q != p:
                raise JPEGDecodeError(f"Expecting value 0x{p.hex()} but was 0x{q.hex()}", stream, stream.tell())

        __expect_bytes(MARKERS['SOI'])
        while True:
            marker = stream.read(2)
            if marker not in MARKERS_MAP:
                raise JPEGDecodeError(f"Unexpected marker 0x{marker.hex()}", stream, stream.tell())
            marker = MARKERS_MAP[marker]
            if marker == 'SOI':
                raise JPEGDecodeError(f"Unexpected marker {marker}", stream, stream.tell())
            if marker == 'EOI':
                break
            L = __read_int16()
            segment = stream.read(L - 2)

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
                    val = stream.read(1)
                    if val == b'\xff': val += stream.read(1)
                    if val == b'\xff\x00': val = b'\xff'
                    if len(val) == 2: # marker
                        stream.seek(-2, 1)
                        break
                    segment.append(val)
                self.decode_ecs(b''.join(segment))
        ensure_eos(stream)
