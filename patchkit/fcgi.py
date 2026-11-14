"""Bounded local FastCGI transport, compatible with Python 3.5+ for legacy VMs."""
import socket
import struct
import time


def record(kind, data=b'', request=1):
    return struct.pack('!BBHHBB', 1, kind, request, len(data), 0, 0) + data


def length(value):
    return bytes([value]) if value < 128 else struct.pack('!I', value | 0x80000000)


def params(values):
    out = bytearray()
    for key, value in values.items():
        key, value = key.encode(), str(value).encode()
        out.extend(length(len(key)) + length(len(value)) + key + value)
    return bytes(out)


def exact(stream, size, deadline=None):
    out = bytearray()
    while len(out) < size:
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('FastCGI deadline exceeded')
            stream.settimeout(remaining)
        chunk = stream.recv(size - len(out))
        if not chunk:
            raise ValueError('truncated FastCGI response')
        out.extend(chunk)
    return bytes(out)


def read_response(stream, request_id=1, maximum=1024*1024, deadline=None):
    out, errors = bytearray(), bytearray()
    total = 0
    while True:
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('FastCGI deadline exceeded')
            stream.settimeout(remaining)
        version, kind, request, size, padding, reserved = struct.unpack('!BBHHBB', exact(stream, 8, deadline))
        total += 8 + size + padding
        if total > maximum or version != 1 or request != request_id:
            raise ValueError('FastCGI protocol or response budget violation')
        data = exact(stream, size, deadline)
        exact(stream, padding, deadline)
        if kind == 6:
            out.extend(data)
        elif kind == 7:
            errors.extend(data)
        elif kind == 3:
            if len(data) != 8:
                raise ValueError('invalid FastCGI END_REQUEST')
            app_status, protocol_status = struct.unpack('!IB3x', data)
            if app_status or protocol_status:
                raise ValueError('FastCGI application failed')
            break
        else:
            raise ValueError('unexpected FastCGI response record')
    header, separator, body = bytes(out).partition(b'\r\n\r\n')
    if not separator:
        raise ValueError('missing CGI response headers')
    status = 200
    for line in header.split(b'\r\n'):
        if line.lower().startswith(b'status:'):
            status = int(line.split(b':', 1)[1].strip().split()[0])
    if status != 200:
        raise ValueError('CGI response status ' + str(status))
    return {'status': status, 'body': body, 'stderr': bytes(errors)}


def request(socket_path, values, body=b'', timeout=10):
    deadline = time.monotonic() + timeout
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as stream:
        stream.settimeout(timeout)
        stream.connect(str(socket_path))
        stream.sendall(record(1, struct.pack('!HB5x', 1, 0)))
        for kind, data in [(4, params(values)), (5, body)]:
            for offset in range(0, len(data), 65535):
                stream.settimeout(max(0.001, deadline - time.monotonic()))
                stream.sendall(record(kind, data[offset:offset+65535]))
            stream.sendall(record(kind))
        return read_response(stream, 1, 1024*1024, deadline)
