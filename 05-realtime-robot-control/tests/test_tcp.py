import socket
import threading
import unittest
from robot_lab.tcp_demo import Arena,Server,exchange


class TcpTests(unittest.TestCase):
    def test_protocol_validation(self):
        arena=Arena()
        self.assertFalse(arena.handle({'type':'dance'})['ok'])
        self.assertFalse(arena.handle({'type':'set_speed','value':99})['ok'])
        self.assertTrue(arena.handle({'type':'telemetry'})['ok'])

    def test_actual_socket_roundtrip(self):
        with Server(('127.0.0.1',0)) as server:
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            with socket.create_connection(server.server_address,timeout=2) as sock:
                with sock.makefile('rwb') as f:
                    reset=exchange(f,{'type':'reset'})
                    self.assertTrue(reset['ok'])
                    self.assertTrue(exchange(f,{'type':'set_speed','value':8})['ok'])
                    telemetry=exchange(f,{'type':'telemetry'})
                    self.assertTrue(telemetry['ok'])
                    self.assertAlmostEqual(telemetry['telemetry']['gap'],43,delta=.3)
                    self.assertTrue(exchange(f,{'type':'brake'})['ok'])
            server.shutdown()
            thread.join(timeout=2)


if __name__ == '__main__': unittest.main()
