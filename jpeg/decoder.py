from io import BytesIO
from struct import unpack
from typing import BinaryIO

class JPEGDecodeError(ValueError):
    """Subclass of ValueError with the following additional properties:

    msg: The unformatted error message
    data: The JPEG data being parsed
    pos: The start index of data where parsing failed

    """
    # Note that this exception is used from _json
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
    return divmod(unpack("B", b)[0], 0x10)

def ensure_range(data: BinaryIO, varname: str, value: int, min_value: int, max_value: int):
    if min_value <= value <= max_value: return
    raise JPEGDecodeError(f"Expecting {varname} in [{min_value}, {max_value}] but was {value}", data, data.tell())

def ensure_eos(data: BinaryIO):
    b = data.read(1)
    if not b: return
    raise JPEGDecodeError(f"Expecting end of segment but 0x{b.hex()} was found", data, data.tell())

def parse_qt(segment: bytes):
    # B.2.4.1 Quantization table-specification syntax
    debug('DQT', len(segment))
    data = BytesIO(segment)
    ret = []
    while True:
        PqTq = data.read(1)
        if not PqTq: break
        Pq, Tq = unpack_int4(PqTq)
        debug('Pq, Tq:', Pq, Tq)
        if Pq == 0:
            Q = unpack("B" * 64, data.read(64))
        elif Pq == 1:
            raise JPEGDecodeError(f"Expecting Pq = 0 for baseline decoding but Pq = 1 was found", data, data.tell())
            Q = unpack(">" + "H" * 64, data.read(128))
        else:
            raise JPEGDecodeError(f"Unknown Pq {Pq}", data, data.tell())
        ensure_range(data, "Tq", Tq, 0, 3)
        ret.append({'Pq': Pq, 'Tq': Tq, 'Q': Q})
    debug(ret)
    debug()
    ensure_eos(data)
    return ret

def parse_ht(segment: bytes):
    # B.2.4.2 Huffman table-specification syntax
    debug('DHT', len(segment))
    data = BytesIO(segment)
    ret = []
    while True:
        TcTh = data.read(1)
        if not TcTh: break
        Tc, Th = unpack_int4(TcTh)
        debug('Tc, Th:', Tc, Th)
        ensure_range(data, "Tc", Tc, 0, 1)
        ensure_range(data, "Th", Th, 0, 1)
        L = unpack("B" * 16, data.read(16))
        debug('L:', L)
        V = [unpack("B" * L[i], data.read(L[i])) for i in range(16)]
        ret.append({'Tc': Tc, 'Th': Th, 'V': V})
    debug(ret)
    debug()
    ensure_eos(data)
    return ret

def parse_sof(segment: bytes):
    # B.2.2 Frame header syntax
    debug('SOF', len(segment))
    data = BytesIO(segment)
    P, Y, X, Nf = unpack(">BHHB", data.read(6))
    debug("P, Y, X, Nf:", P, Y, X, Nf)
    CHVTq = []
    for _ in range(Nf):
        C, HV, Tq = unpack("BBB", data.read(3))
        H, V = divmod(HV, 0x10)
        ensure_range(data, "H", H, 1, 4)
        ensure_range(data, "V", V, 1, 4)
        ensure_range(data, "Tq", Tq, 0, 3)
        CHVTq.append({"C": C, "H": H, "V": V, "Tq": Tq})
    ret = {
        'P': P,
        'Y': Y,
        'X': X,
        'CHVTq': CHVTq,
    }
    debug(ret)
    debug()
    ensure_eos(data)
    return ret

def parse_sos(segment: bytes):
    # B.2.3 Scan header syntax
    debug('SOS', len(segment))
    data = BytesIO(segment)
    Ns = unpack("B", data.read(1))[0]
    debug("Ns:", Ns)
    ensure_range(data, "Ns", Ns, 1, 4)
    CsTdTa = []
    for _ in range(Ns):
        Cs, TdTa = unpack("BB", data.read(2))
        Td, Ta = divmod(TdTa, 0x10)
        CsTdTa.append({'Cs': Cs, 'Td': Td, 'Ta': Ta})
        ensure_range(data, 'Td', Td, 0, 1)
        ensure_range(data, 'Ta', Ta, 0, 1)
    Ss, Se = unpack("BB", data.read(2))
    ensure_range(data, "Ss", Ss, 0, 0)
    ensure_range(data, "Se", Se, 63, 63)
    Ah, Al = unpack_int4(data.read(1))
    ensure_range(data, "Ah", Ah, 0, 0)
    ensure_range(data, "Al", Al, 0, 0)
    ret = {
        'CsTdTa': CsTdTa,
        'Ss': Ss,
        'Se': Se,
        'Ah': Ah,
        'Al': Al,
    }
    debug(ret)
    debug()
    ensure_eos(data)
    return ret

def decode(data: BinaryIO):
    def __read_int16():
        return unpack(">H", data.read(2))[0]

    def __expect_bytes(p: bytes):
        q = data.read(len(p))
        if q != p:
            raise JPEGDecodeError(f"Expecting value 0x{p.hex()} but was 0x{q.hex()}", data, data.tell())

    __expect_bytes(MARKERS['SOI'])
    glob_qt = {}
    dc_ht = {}
    ac_ht = {}
    while True:
        marker = data.read(2)
        if marker not in MARKERS_MAP:
            raise JPEGDecodeError(f"Unexpected marker 0x{marker.hex()}", data, data.tell())
        marker = MARKERS_MAP[marker]

        if marker == 'SOI' or marker == 'EOI':
            raise JPEGDecodeError(f"Unexpected marker {marker}", data, data.tell())
        
        L = __read_int16()
        segment = data.read(L - 2)

        if marker == 'APP0' or marker == 'COM':
            continue

        if marker == 'DQT':
            for qt in parse_qt(segment):
                glob_qt[qt["Tq"]] = qt["Q"]
            del qt
        elif marker == 'SOF0':
            sof = parse_sof(segment)
            csp = {}
            for x in sof["CHVTq"]:
                csp[x["C"]] = x
        elif marker == 'DHT':
            for ht in parse_ht(segment):
                if ht["Tc"] == 0:
                    dc_ht[ht["Th"]] = ht["V"]
                else:
                    ac_ht[ht["Th"]] = ht["V"]
            del ht
        elif marker == 'SOS':
            sos = parse_sos(segment)
            debug('QT:', glob_qt)
            debug('AC:', dc_ht)
            debug('HT:', ac_ht)
            debug('Components:', csp)
            debug(len(data.read()))
    return
    data = bytearray(data[idx:]) # entropy-coded segment
    idx = i = 0
    while i < len(data):
        if data[i] != 0xff:
            data[idx] = data[i]
            i, idx = i + 1, idx + 1
        elif data[i + 1] == 0xd9: # EOI
            break
        elif data[i + 1] == 0x00:
            data[idx] = 0xff
            i, idx = i + 2, idx + 1
        else:
            raise JPEGDecodeError(f"Unexpected marker 0xff{data[i + 1]:02x} in scan", data, i)
