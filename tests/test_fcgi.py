import socket
import struct
import threading
import time
import unittest
from patchkit import fcgi


def record(kind, data=b'', request=1):
    return struct.pack('!BBHHBB', 1, kind, request, len(data), 0, 0) + data


class FastCGITests(unittest.TestCase):
    def exchange(self, data):
        a, b = socket.socketpair()
        self.addCleanup(a.close)
        self.addCleanup(b.close)
        b.sendall(data)
        b.shutdown(socket.SHUT_WR)
        return a

    def test_reads_successful_response(self):
        stream = self.exchange(record(6, b'Content-Type: text/plain\r\n\r\nOK') + record(3, b'\0'*8))
        self.assertEqual(fcgi.read_response(stream, 1, 1024)['body'], b'OK')

    def test_http_failure_is_not_success(self):
        stream = self.exchange(record(6, b'Status: 500 Error\r\n\r\nfailed') + record(3, b'\0'*8))
        with self.assertRaises(ValueError):
            fcgi.read_response(stream, 1, 1024)

    def test_application_failure_rejected(self):
        stream = self.exchange(record(3, struct.pack('!IB3x', 1, 0)))
        with self.assertRaises(ValueError):
            fcgi.read_response(stream, 1, 1024)

    def test_truncated_response_rejected(self):
        with self.assertRaises(ValueError):
            fcgi.read_response(self.exchange(record(6, b'partial')), 1, 1024)

    def test_wrong_request_id_rejected(self):
        with self.assertRaises(ValueError):
            fcgi.read_response(self.exchange(record(6, b'wrong', 2)), 1, 1024)

    def test_response_budget_enforced(self):
        with self.assertRaises(ValueError):
            fcgi.read_response(self.exchange(record(6, b'x'*100)), 1, 50)

    def test_long_parameter_uses_four_byte_encoding(self):
        encoded = fcgi.params({'X': 'a'*128})
        self.assertEqual(encoded[:5], b'\x01\x80\x00\x00\x80')

    def test_empty_record_stream_rejected(self):
        with self.assertRaises(ValueError):
            fcgi.read_response(self.exchange(b''), 1, 1024)

    def test_trickle_cannot_extend_absolute_deadline(self):
        a, b = socket.socketpair()
        self.addCleanup(a.close)
        self.addCleanup(b.close)
        def slow():
            for value in record(6, b'slow'):
                try:
                    b.sendall(bytes([value]))
                except OSError:
                    return
                time.sleep(0.02)
        thread = threading.Thread(target=slow, daemon=True)
        thread.start()
        started = time.monotonic()
        with self.assertRaises(TimeoutError):
            fcgi.read_response(a, 1, 1024, started + 0.06)
        self.assertLess(time.monotonic() - started, 0.15)


if __name__ == '__main__':
    unittest.main()
