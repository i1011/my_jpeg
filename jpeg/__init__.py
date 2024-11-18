from io import BytesIO
from typing import BinaryIO

from .decoder import decode

def load(file: BinaryIO):
    decode(file)

def loads(data: bytes):
    return load(BytesIO(data))

__all__ = [
    'loads',
    'load',
]
