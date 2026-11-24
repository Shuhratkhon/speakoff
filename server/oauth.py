"""Sign in with Google / Apple.

The browser (or later the phone app) signs the user in with Google or Apple and sends us a token; we check the token
with Google / Apple and get the account's id ("sub") and e-mail. Nothing works until the IDs are set (see README):

  GOOGLE_CLIENT_IDS   comma-separated OAuth client IDs (web, Android, iOS)     e.g. 123-abc.apps.googleusercontent.com
  APPLE_CLIENT_IDS    comma-separated: the web Services ID and the iOS bundle ID e.g. com.speakoff.signin,com.speakoff.app
  APPLE_REDIRECT_URI  the HTTPS return address registered for the Services ID  e.g. https://speakoff.duckdns.org/
"""

import os

import requests

GOOGLE_IDS = [x.strip() for x in os.environ.get("GOOGLE_CLIENT_IDS", "").split(",") if x.strip()]
APPLE_IDS = [x.strip() for x in os.environ.get("APPLE_CLIENT_IDS", "").split(",") if x.strip()]
APPLE_REDIRECT = os.environ.get("APPLE_REDIRECT_URI", "")
_apple_keys = None


class OAuthError(Exception):
    pass


def public_config():
    """What the page needs to show working buttons (None = not set up on this server)."""
    return {"google": GOOGLE_IDS[0] if GOOGLE_IDS else None,
            "apple": {"client_id": APPLE_IDS[0], "redirect_uri": APPLE_REDIRECT} if APPLE_IDS and APPLE_REDIRECT else None}


def _google(token, kind):
    """kind = 'id_token' (phone apps, Google button) or 'access_token' (our own web button)."""
    if not GOOGLE_IDS:
        raise OAuthError("not_configured")
    r = requests.get("https://oauth2.googleapis.com/tokeninfo", params={kind: token}, timeout=10)
    if r.status_code != 200:
        raise OAuthError("bad_token")
    info = r.json()
    if info.get("aud") not in GOOGLE_IDS and info.get("azp") not in GOOGLE_IDS:
        raise OAuthError("wrong_app")
    if info.get("iss") and info["iss"] not in ("accounts.google.com", "https://accounts.google.com"):
        raise OAuthError("bad_token")
    if not info.get("sub"):
        raise OAuthError("bad_token")
    return {"sub": info["sub"], "email": (info.get("email") or "").lower() or None,
            "email_verified": str(info.get("email_verified")).lower() == "true"}


def _apple(token):
    global _apple_keys
    import jwt
    if not APPLE_IDS:
        raise OAuthError("not_configured")
    if _apple_keys is None:
        _apple_keys = jwt.PyJWKClient("https://appleid.apple.com/auth/keys")
    try:
        key = _apple_keys.get_signing_key_from_jwt(token)
        info = jwt.decode(token, key.key, algorithms=["RS256"], audience=APPLE_IDS, issuer="https://appleid.apple.com")
    except Exception as e:
        raise OAuthError("bad_token") from e
    return {"sub": info["sub"], "email": (info.get("email") or "").lower() or None,
            "email_verified": str(info.get("email_verified")).lower() == "true"}


def verify(provider, token, kind="id_token"):
    if not token or provider not in ("google", "apple"):
        raise OAuthError("bad_token")
    return _google(token, kind if kind in ("id_token", "access_token") else "id_token") if provider == "google" \
        else _apple(token)
