import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('canal_pairing', Path(__file__).resolve().parents[1] / 'addon/globalPlugins/tvpVod/canal_pairing.py')
pairing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pairing)


class Response:
    def __init__(self, value):
        self.raw = value.encode() if isinstance(value, str) else json.dumps(value).encode()
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, limit): return self.raw[:limit]


class Opener:
    def __init__(self, *values): self.values, self.requests = list(values), []
    def open(self, request, timeout):
        self.requests.append(request)
        return Response(self.values.pop(0))


def page(zone='cppol'):
    return '<script id="__NEXT_DATA__" type="application/json">' + json.dumps({
        'props': {'appData': {'deviceId': 'test-device', 'offerLocation': 'pl', 'offerZone': zone}}
    }) + '</script>'


class PairingTests(unittest.TestCase):
    def test_pending_is_throttled_and_expiration_stops_network(self):
        opener = Opener(page(), {'authenticationToken': 'ABCDE'}, {'errorCode': 56})
        now = [0]
        client = pairing.CodePairing(opener, lambda: now[0])
        self.assertEqual(client.begin(), 'ABCDE')
        self.assertIsNone(client.poll())
        self.assertIsNone(client.poll())
        self.assertEqual(len(opener.requests), 3)
        now[0] = 300
        with self.assertRaises(pairing.PairingError): client.poll()
        self.assertEqual(len(opener.requests), 3)
        self.assertIsNone(client._code)

    def test_wrong_region_does_not_generate_code(self):
        opener = Opener(page('cpfra'))
        with self.assertRaises(pairing.PairingError): pairing.CodePairing(opener).begin()
        self.assertEqual(len(opener.requests), 1)

    def test_success_clears_code_and_does_not_make_it_reusable(self):
        opener = Opener(page(), {'authenticationToken': 'ABCDE'}, {'errorCode': 0, 'testSession': 'private'})
        client = pairing.CodePairing(opener)
        client.begin()
        self.assertEqual(client.poll()['testSession'], 'private')
        with self.assertRaises(pairing.PairingError): client.poll()
        self.assertEqual(len(opener.requests), 3)

    def test_error_does_not_disclose_server_response(self):
        opener = Opener(page(), {'authenticationToken': 'ABCDE'}, {'errorCode': 99, 'errorMessage': 'private'})
        client = pairing.CodePairing(opener)
        client.begin()
        with self.assertRaises(pairing.PairingError) as caught: client.poll()
        self.assertNotIn('private', str(caught.exception))

    def test_redirect_rejects_untrusted_destination(self):
        for target in ('http://account.canalplus.com/', 'https://account.canalplus.com.evil/', 'https://u@account.canalplus.com/', 'https://account.canalplus.com:8443/'):
            with self.assertRaises(pairing.PairingError):
                pairing.AccountRedirect().redirect_request(None, None, 302, '', {}, target)
