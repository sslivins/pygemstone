"""Public Gemstone Lights cloud constants.

These values are the same for every Gemstone Lights customer — they
identify the backend, not the user — and are trivially recoverable
from a decompiled APK / IPA or any packet capture of the official
mobile app. They are NOT secrets.

The endpoints below were derived from a capture of the official iOS
app (``com.gemstone.lights``, app version 0.6.03) talking to its
AWS Amplify (Cognito + API Gateway + AppSync) backend in
``us-west-2``.
"""

from __future__ import annotations

# AWS region the Gemstone backend lives in.
AWS_REGION: str = "us-west-2"

# Cognito User Pool used for end-user authentication.
COGNITO_USER_POOL_ID: str = "us-west-2_rr5lY7Etr"

# Cognito App Client ID. The official app does NOT use a client secret
# (this is a public mobile app client), so SRP auth needs only this id.
COGNITO_CLIENT_ID: str = "2647t144niotrl53vvru0ivno7"

# REST API base. All control-plane endpoints live under ``/prod``.
REST_API_BASE: str = (
    "https://mytpybpq12.execute-api.us-west-2.amazonaws.com/prod"
)

# AppSync GraphQL endpoint (HTTP queries / mutations).
APPSYNC_API_URL: str = (
    "https://uaa3jxaxnvghha5qeyb254furu.appsync-api.us-west-2.amazonaws.com/graphql"
)

# AppSync GraphQL realtime endpoint (WebSocket subscriptions).
APPSYNC_REALTIME_URL: str = (
    "wss://uaa3jxaxnvghha5qeyb254furu.appsync-realtime-api.us-west-2.amazonaws.com/graphql"
)

# User-Agent string we send. The official app uses ``Dart/3.9 (dart:io)``
# for its REST traffic; we identify ourselves honestly so a Gemstone
# operator can tell unofficial clients apart from the real app.
USER_AGENT: str = "pygemstone/0.0.1 (+https://github.com/sslivins/pygemstone)"

# Default per-request timeout (seconds).
DEFAULT_TIMEOUT: float = 30.0
