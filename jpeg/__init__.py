
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

def parse_segments(data: bytes):
    idx = 0

    def __read(count: int):
        nonlocal idx
        if idx + count > len(data):
            raise JPEGDecodeError(f"Expecting {count} bytes but {len(data) - idx} was found", data, idx)
        ret = data[idx:idx + count]
        idx += count
        return ret
    
    def __read_int16():
        return int.from_bytes(__read(2), 'big')

    def __expect_bytes(p: bytes):
        q = __read(len(p))
        if q != p:
            raise JPEGDecodeError(f"Expecting value 0x{p.hex()} but was 0x{q.hex()}", data, idx - len(q))

    __expect_bytes(MARKERS['SOI'])
    ret = []
    while True:
        marker = __read(2)
        if marker not in MARKERS_MAP:
            raise JPEGDecodeError(f"Unexpected marker 0x{marker.hex()}", data, idx - len(marker))
        marker = MARKERS_MAP[marker]
        if marker == 'SOI' or marker == 'EOI':
            raise JPEGDecodeError(f"Unexpected marker {marker}", data, idx - len(marker))
        L = __read_int16()
        header = __read(L - 2)
        ret.append((marker, header))
        if marker == 'SOS':
            break
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
    ret.append(('coded_seg', data))
    return ret

def loads(data: bytes):
    segments = parse_segments(data)
    print(segments)

__all__ = [
    'loads',
    'JPEGDecodeError',
]
