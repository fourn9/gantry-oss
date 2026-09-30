import json
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import urlsplit
from .model import Fault, canonical, uid


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_url(url):
    parsed = urlsplit(url)
    if (parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment):
        raise Fault('invalid_input', 'Use an HTTP(S) Gantry URL without credentials, query or fragment')
    if parsed.scheme == 'http' and parsed.hostname not in {'127.0.0.1', 'localhost', '::1'}:
        raise Fault('insecure_transport', 'Non-loopback connections require HTTPS')
    return url.rstrip('/')


class Client:
    def __init__(self, url, token):
        self.url, self.token = validate_url(url), token
        self.opener = build_opener(NoRedirect())

    def call(self, command, arguments=None, key=None):
        request = Request(self.url + "/v1/commands/" + command,
                          data=canonical(arguments or {}).encode(), method="POST",
                          headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json",
                                   "Idempotency-Key": key or uid("request")})
        try:
            with self.opener.open(request, timeout=45) as response:
                return json.load(response)["result"]
        except HTTPError as exc:
            if exc.code in {408,429,502,503,504}:
                raise Fault('rate_limited' if exc.code==429 else 'temporarily_unavailable', 'HTTP '+str(exc.code)) from exc
            try: error = json.load(exc)["error"]
            except Exception: raise Fault("http_error", "HTTP " + str(exc.code)) from exc
            raise Fault(error["code"], error.get("message", "Request failed"), error.get("details")) from exc
