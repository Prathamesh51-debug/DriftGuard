"""
Fault F4: Duplicate Invoice (stub — to be implemented next).
"""
from mitmproxy import http

def arm_request(flow: http.HTTPFlow):
    pass

def inject_response(flow: http.HTTPFlow) -> bool:
    return False

