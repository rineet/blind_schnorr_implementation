from typing import Tuple, Optional
from binascii import unhexlify
import hashlib
import os


p = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
n = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
G = (0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
     0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8)

Point = Tuple[int, int]

def bytes_from_int(a: int) -> bytes:
    return a.to_bytes(32, byteorder="big")

def bytes_from_hex(a: hex) -> bytes:
    return unhexlify(a)

def bytes_from_point(P: Point) -> bytes:
    return bytes_from_int(x(P))


def int_from_bytes(b: bytes) -> int:
    return int.from_bytes(b, byteorder="big")

def int_from_hex(a: hex) -> int:
    return int.from_bytes(unhexlify(a), byteorder="big")

def x(P: Point) -> int:
    return P[0]

def y(P: Point) -> int:
    return P[1]

def point_add(P1: Optional[Point], P2: Optional[Point]) -> Optional[Point]:
    
    if P1 is None:
        return P2
    if P2 is None:
        return P1
    if (x(P1) == x(P2)) and (y(P1) != y(P2)):
        return None
    if P1 == P2:
        lam = (3 * x(P1) * x(P1) * pow(2 * y(P1), p - 2, p)) % p
    else:
        lam = ((y(P2) - y(P1)) * pow(x(P2) - x(P1), p - 2, p)) % p
    x3 = (lam * lam - x(P1) - x(P2)) % p
    y3=(lam * (x(P1) - x3) - y(P1)) % p
    
    return x3,y3

def point_mul(P: Optional[Point], d: int) -> Optional[Point]:

    R = None
    for i in range(256):
        if (d >> i) & 1:
            R = point_add(R, P)
        P = point_add(P, P)

    return R

def tagged_hash(tag: str, msg: bytes) -> bytes:
    tag_hash = hashlib.sha256(tag.encode()).digest()
    return hashlib.sha256(tag_hash + tag_hash + msg).digest()

def is_infinity(P: Optional[Point]) -> bool:
    return P is None

def xor_bytes(b0: bytes, b1: bytes) -> bytes:
    return bytes(a ^ b for (a, b) in zip(b0, b1))


# fermats little theorem to check whether to calculate sq root of y
def lift_x_square_y(b: bytes) -> Optional[Point]:
    x = int_from_bytes(b)
    # if x >= p:
    #     return None
    y_sq = (pow(x, 3, p) + 7) % p
    y = pow(y_sq, (p + 1) // 4, p)
    # if pow(y, 2, p) != y_sq:
    #     return None
    return x, y


def lift_x_even_y(b: bytes) -> Optional[Point]:
    P = lift_x_square_y(b)
    if P is None:
        return None
    else:
        return x(P), y(P) if y(P) % 2 == 0 else p - y(P)


def sha256(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()

# square in modular arithmetic 2^3%7==1 so 2 is square
def is_square(a: int) -> bool:
    return int(pow(a, (p - 1) // 2, p)) == 1


# Check if a point has square y coordinate
def has_square_y(P: Optional[Point]) -> bool:
    infinity = is_infinity(P)
    if infinity:
        return False
    assert P is not None
    return is_square(y(P))


# Check if a point has even y coordinate
def has_even_y(P: Point) -> bool:
    return y(P) % 2 == 0


# Generate public key from an int
def pubkey_gen_from_int(seckey: int) -> bytes:
    P = point_mul(G, seckey)
    assert P is not None
    return bytes_from_point(P)

# Generate public key from a hex
def pubkey_gen_from_hex(seckey: hex) -> bytes:
    seckey = bytes.fromhex(seckey)
    d0 = int_from_bytes(seckey)
    if not (1 <= d0 <= n - 1):
        raise ValueError(
            'The secret key must be an integer in the range 1..n-1.')
    P = point_mul(G, d0)
    assert P is not None
    return bytes_from_point(P)


# Generate public key (as a point) from an int
def pubkey_point_gen_from_int(seckey: int) -> Point:
    P = point_mul(G, seckey)
    assert P is not None
    return P


def get_aux_rand() -> bytes:
    return os.urandom(32)


# Extract R_x int value from signature
def get_int_R_from_sig(sig: bytes) -> int:
    return int_from_bytes(sig[0:32])


# Extract s int value from signature
def get_int_s_from_sig(sig: bytes) -> int:
    return int_from_bytes(sig[32:64])

# Extract R_x bytes from signature
def get_bytes_R_from_sig(sig: bytes) -> int:
    return sig[0:32]


# Extract s bytes from signature
def get_bytes_s_from_sig(sig: bytes) -> int:
    return sig[32:64]

# Generate Schnorr signature
def schnorr_sign(msg: bytes, privateKey: str) -> bytes:
    if len(msg) != 32:
        raise ValueError('The message must be a 32-byte array.')
    d0 = int_from_hex(privateKey)
    if not (1 <= d0 <= n - 1):
        raise ValueError('The secret key must be an integer in the range 1..n-1.')
    P = point_mul(G, d0)
    assert P is not None
    d = d0 if has_even_y(P) else n - d0
    t = xor_bytes(bytes_from_int(d), tagged_hash("BIP0340/aux", get_aux_rand()))
    k0 = int_from_bytes(tagged_hash("BIP0340/nonce", t + bytes_from_point(P) + msg)) % n
    if k0 == 0:
        raise RuntimeError('Failure. This happens only with negligible probability.')
    R = point_mul(G, k0)
    assert R is not None
    k = n - k0 if not has_even_y(R) else k0
    e = int_from_bytes(tagged_hash("BIP0340/challenge", bytes_from_point(R) + bytes_from_point(P) + msg)) % n
    sig = bytes_from_point(R) + bytes_from_int((k + e * d) % n)
    
    if not schnorr_verify(msg, bytes_from_point(P), sig):
        raise RuntimeError('The created signature does not pass verification.')
    return sig

# Verify Schnorr signature
def schnorr_verify(msg: bytes, pubkey: bytes, sig: bytes) -> bool:

    if len(msg) != 32:
        raise ValueError('The message must be a 32-byte array.')
    if len(pubkey) != 32:
        raise ValueError('The public key must be a 32-byte array.')
    if len(sig) != 64:
        raise ValueError('The signature must be a 64-byte array.')
    P = lift_x_even_y(pubkey)
    r = get_int_R_from_sig(sig)
    s = get_int_s_from_sig(sig)
    if (P is None) or (r >= p) or (s >= n):
        return False
    e = int_from_bytes(tagged_hash("BIP0340/challenge", get_bytes_R_from_sig(sig) + pubkey + msg)) % n
    R = point_add(point_mul(G, s), point_mul(P, n - e))
    if (R is None) or (not has_even_y(R)):
        return False
    if x(R) != r:
        return False
    
    return True
