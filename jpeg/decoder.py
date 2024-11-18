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

def parse_qt(segment: bytes):
    # B.2.4.1 Quantization table-specification syntax
    debug('DQT', len(segment))
    data = BytesIO(segment)
    ret = []
    while True:
        PqTq = data.read(1)
        if not PqTq: break
        Pq, Tq = divmod(unpack("B", PqTq)[0], 16)
        debug('Pq Tq:', Pq, Tq)
        if Pq == 0:
            Q = unpack("B" * 64, data.read(64))
        elif Pq == 1:
            raise JPEGDecodeError(f"Expecting Pq = 0 for baseline decoding but Pq = 1 was found", data, data.tell())
            Q = unpack(">H" * 64, data.read(128))
        else:
            raise JPEGDecodeError(f"Unknown Pq {Pq}", data, data.tell())
        ret.append({'Tq': Tq, 'Q': Q})
    debug(ret)
    debug()
    return ret

def parse_ht(segment: bytes):
    # B.2.4.2 Huffman table-specification syntax
    debug('DHT', len(segment))
    data = BytesIO(segment)
    Tc, Th = divmod(unpack("B", data.read(1))[0], 16)
    debug('Tc Th:', Tc, Th)
    if Tc not in [0, 1]:
        raise JPEGDecodeError(f"Expecting Tc in [0, 1] but was {Tc}", data, data.tell())
    L = unpack("B" * 16, data.read(16))
    debug('L:', L)
    V = [unpack("B" * L[i], data.read(L[i])) for i in range(16)]
    debug('V:', V)
    debug()
    return {'Tc': Tc, 'Th': Th, 'V': V}

def decode(data: BinaryIO):
    def __read_int16():
        return unpack(">H", data.read(2))[0]

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

        if marker == 'SOI' or marker == 'EOI':
            raise JPEGDecodeError(f"Unexpected marker {marker}", data, data.tell())
        
        L = __read_int16()
        segment = data.read(L - 2)

        if marker == 'APP0' or marker == 'COM':
            continue

        if marker == 'DQT':
            qts = parse_qt(segment)
        elif marker == 'SOF0':
            pass
        elif marker == 'DHT':
            ht = parse_ht(segment)
        if marker == 'SOS':
            break
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
