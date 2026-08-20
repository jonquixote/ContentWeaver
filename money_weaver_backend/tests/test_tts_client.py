"""Integration tests for src/services/tts_client.py against a live mock TTS server."""
import json
import os
import socket
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

from src.services import tts_client


class MockTTSHandler(BaseHTTPRequestHandler):
    """Configurable stand-in for the MOSS-TTS microservice bound to /tts + /health."""

    tts_status = 200
    tts_body = b'RIFF\x00fake-wav-bytes\x00'
    health_payload = {'ok': True, 'model_ready': True}
    last_request = None

    def do_GET(self):
        if self.path.startswith('/health'):
            payload = json.dumps(self.health_payload).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length) if length else b''
        self.__class__.last_request = json.loads(body) if body else {}
        self.send_response(self.tts_status)
        if self.tts_status == 200:
            self.send_header('Content-Type', 'audio/wav')
            self.send_header('Content-Length', str(len(self.tts_body)))
            self.end_headers()
            self.wfile.write(self.tts_body)
        else:
            self.send_header('Content-Type', 'application/json')
            msg = json.dumps({'detail': 'mock error'}).encode()
            self.send_header('Content-Length', str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)

    def log_message(self, *args):
        pass


class TTSCientTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), MockTTSHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        tts_client.TTS_URL = f'http://127.0.0.1:{cls.port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        MockTTSHandler.tts_status = 200
        MockTTSHandler.health_payload = {'ok': True, 'model_ready': True}
        MockTTSHandler.last_request = None


class TestTTSHealth(TTSCientTestBase):
    def test_health_true_when_model_ready(self):
        self.assertTrue(tts_client.tts_health())

    def test_health_false_when_model_not_ready(self):
        MockTTSHandler.health_payload = {'ok': True, 'model_ready': False}
        self.assertFalse(tts_client.tts_health())

    def test_health_false_on_http_error(self):
        MockTTSHandler.health_payload = {'nope': True}
        self.assertFalse(tts_client.tts_health())

    def test_health_false_when_server_down(self):
        from unittest import mock
        with mock.patch.object(tts_client, 'TTS_URL', 'http://127.0.0.1:1'):
            self.assertFalse(tts_client.tts_health())


class TestSynthesize(TTSCientTestBase):
    def test_returns_wav_bytes_on_200(self):
        MockTTSHandler.tts_body = b'RIFF\x00\x01\x02wav-data'
        out = tts_client.synthesize('hello', '/tmp/ref.wav', voice_id='42')
        self.assertEqual(out, b'RIFF\x00\x01\x02wav-data')

    def test_posts_expected_payload(self):
        tts_client.synthesize('spoken text', '/abs/path/ref.wav', voice_id='7')
        self.assertEqual(MockTTSHandler.last_request, {
            'text': 'spoken text',
            'reference_audio_url': '/abs/path/ref.wav',
            'voice_id': '7',
        })

    def test_voice_id_none_is_sent_as_null(self):
        tts_client.synthesize('t', '/abs/path/ref.wav')
        self.assertIsNone(MockTTSHandler.last_request['voice_id'])

    def test_drops_error_status_400(self):
        MockTTSHandler.tts_status = 400
        with self.assertRaises(requests.HTTPError):
            tts_client.synthesize('t', '/abs/path/ref.wav')

    def test_moss_5xx_falls_back_to_edge(self):
        from unittest import mock
        for code in (502, 503, 500):
            MockTTSHandler.tts_status = code
            with mock.patch.object(tts_client, '_edge_synthesize_sync', return_value=b'EDGE-MP3') as edge:
                out = tts_client.synthesize('t', '/abs/path/ref.wav')
            self.assertEqual(out, b'EDGE-MP3')
            edge.assert_called_once()

    def test_moss_5xx_raises_when_edge_also_fails(self):
        from unittest import mock
        for code in (502, 503, 500):
            MockTTSHandler.tts_status = code
            with mock.patch.object(tts_client, '_edge_synthesize_sync', side_effect=RuntimeError('edge down')):
                with self.assertRaises(requests.HTTPError):
                    tts_client.synthesize('t', '/abs/path/ref.wav')

    def test_moss_connection_error_falls_back_to_edge(self):
        from unittest import mock
        with mock.patch.object(tts_client, 'TTS_URL', 'http://127.0.0.1:1'):
            with mock.patch.object(tts_client, '_edge_synthesize_sync', return_value=b'EDGE-MP3') as edge:
                out = tts_client.synthesize('t', '/abs/path/ref.wav')
        self.assertEqual(out, b'EDGE-MP3')
        edge.assert_called_once()

    def test_moss_connection_error_raises_when_edge_also_fails(self):
        from unittest import mock
        with mock.patch.object(tts_client, 'TTS_URL', 'http://127.0.0.1:1'):
            with mock.patch.object(tts_client, '_edge_synthesize_sync', side_effect=RuntimeError('edge down')):
                with self.assertRaises(requests.RequestException):
                    tts_client.synthesize('t', '/abs/path/ref.wav')

    def test_rejects_unknown_voice_engine(self):
        with self.assertRaises(ValueError):
            tts_client.synthesize('t', '/abs/path/ref.wav', voice_engine='klingon')


class TestTTSURLNormalization(unittest.TestCase):
    def test_trailing_slash_is_stripped(self):
        with unittest.mock.patch.object(tts_client, 'TTS_URL', 'http://example.test:9999/'):
            self.assertEqual(tts_client._base_url(), 'http://example.test:9999')


if __name__ == '__main__':
    unittest.main()