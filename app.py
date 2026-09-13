import os

import requests
from flask import Flask, Response, request

UPSTREAM = os.environ.get("TELEGRAM_API_URL", "https://api.telegram.org")
TIMEOUT = (10, 600)  # connect, read

app = Flask(__name__)

HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host",
    "content-encoding", "content-length",
}

session = requests.Session()


@app.route("/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
@app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
def proxy(path):
    url = f"{UPSTREAM}/{path}"
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in HOP_BY_HOP
    }

    try:
        upstream = session.request(
            method=request.method,
            url=url,
            headers=headers,
            params=request.args,
            data=request.get_data(),
            stream=True,
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        return Response(
            f'{{"ok": false, "error_code": 502, "description": "Upstream error: {exc}"}}',
            status=502,
            mimetype="application/json",
        )

    resp_headers = [
        (k, v) for k, v in upstream.headers.items()
        if k.lower() not in HOP_BY_HOP
    ]
    return Response(upstream.iter_content(chunk_size=64 * 1024), status=upstream.status_code, headers=resp_headers)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
