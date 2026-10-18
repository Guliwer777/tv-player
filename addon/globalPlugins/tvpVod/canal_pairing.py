"""Experimental CANAL+ code pairing transport; not yet wired to playback.

Requests follow the public Polish account site's TV login page. Credentials,
cookies and returned session data must never be logged. No session is persisted
here, and successful pairing alone does not establish playback entitlement.
"""
import http.cookiejar
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://account.canalplus.com'
PAGE = BASE + '/pl/pl/tvscreen/login/code?display=tv&media=web&offerZone=cppol'
CONNECT = BASE + '/pl/pl/connect'
LIFETIME = 300


class PairingError(Exception):
    pass


class AccountRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urlsplit(newurl)
        if (target.scheme != 'https' or target.hostname != 'account.canalplus.com'
                or target.username or target.password or target.port not in (None, 443)):
            raise PairingError('Nieoczekiwane przekierowanie logowania CANAL+.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class CodePairing:
    def __init__(self, opener=None, clock=time.monotonic):
        self._opener = opener or urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()), AccountRedirect())
        self._clock = clock
        self._device = None
        self._code = None
        self._expires = 0
        self._next_poll = 0

    def _request(self, path, fields=None):
        headers = {'User-Agent': 'Mozilla/5.0', 'Referer': PAGE, 'Origin': BASE}
        data = None
        if fields is not None:
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            data = urllib.parse.urlencode(fields).encode('utf-8')
        request = urllib.request.Request(BASE + path, data=data, headers=headers)
        try:
            with self._opener.open(request, timeout=15) as response:
                raw = response.read(1_000_001)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            # Exception strings or response bodies can contain session material.
            raise PairingError('Nie udało się połączyć z logowaniem CANAL+.') from None
        if len(raw) > 1_000_000:
            raise PairingError('Zbyt duża odpowiedź logowania CANAL+.')
        return raw

    def _post(self, path, fields):
        try:
            value = json.loads(self._request(path, fields))
        except (ValueError, UnicodeError):
            raise PairingError('Nieprawidłowa odpowiedź logowania CANAL+.') from None
        if not isinstance(value, dict):
            raise PairingError('Nieprawidłowa odpowiedź logowania CANAL+.')
        return value

    def begin(self):
        self.cancel()
        raw = self._request(PAGE[len(BASE):]).decode('utf-8', errors='replace')
        match = re.search(r'<script\s+id="__NEXT_DATA__"[^>]*>(.*?)</script>', raw, re.S)
        try:
            app = json.loads(match[1])['props']['appData'] if match else {}
            device = app['deviceId']
            if (app.get('offerLocation') != 'pl' or app.get('offerZone') != 'cppol'
                    or not isinstance(device, str) or not re.fullmatch(r'[\w-]{1,128}', device)):
                raise ValueError()
        except (KeyError, TypeError, ValueError):
            raise PairingError('Nie potwierdzono polskiej sesji logowania CANAL+.') from None
        result = self._post('/api/pass/generateAuthenticationToken', {'deviceId': device})
        code = result.get('authenticationToken')
        if not isinstance(code, str) or not re.fullmatch(r'[A-Za-z0-9]{5}', code):
            raise PairingError('CANAL+ nie wydał prawidłowego kodu.')
        self._device, self._code = device, code
        self._expires = self._clock() + LIFETIME
        return code

    def poll(self):
        """Return None while pending, or the private success response in memory."""
        now = self._clock()
        if not self._code or now >= self._expires:
            self.cancel()
            raise PairingError('Kod CANAL+ wygasł lub został anulowany.')
        if now < self._next_poll:
            return None
        self._next_poll = now + 5
        result = self._post('/api/pass/loginByAuthenticationToken', {
            'authenticationToken': self._code, 'deviceId': self._device})
        error = result.get('errorCode')
        if error == 56:  # Observed response for our own unapproved code.
            return None
        if error == 0:
            self.cancel()
            return result
        self.cancel()
        raise PairingError('CANAL+ nie zatwierdził logowania kodem.')

    def cancel(self):
        self._device = self._code = None
        self._expires = self._next_poll = 0
