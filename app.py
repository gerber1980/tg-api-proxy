import os
import re

import requests
from flask import Flask, Response, request

UPSTREAM = os.environ.get("TELEGRAM_API_URL", "https://api.telegram.org")
SECRET_PATH = os.environ.get("SECRET_PATH", "").strip("/")
MAX_BODY_SIZE = 50 * 1024 * 1024  # лимит Telegram на загрузку файлов
TIMEOUT = (10, 600)  # connect, read

app = Flask(__name__)
app.url_map.strict_slashes = False

HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host",
    "content-encoding", "content-length",
}

# Рабочие пути Bot API: /bot<TOKEN>/method и /file/bot<TOKEN>/<path>
BOT_RE = re.compile(r"^(file/)?bot\d+:[A-Za-z0-9_-]{20,}(/|$)")

session = requests.Session()


def not_found():
    return Response('{"ok": false, "error_code": 404, "description": "Not Found"}',
                    status=404, mimetype="application/json")


@app.route("/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
@app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
def proxy(path):
    target = path

    if SECRET_PATH:
        # Допустимы только /<секрет>/bot.../... ; всё остальное, включая /, — 404
        parts = path.split("/", 1)
        if len(parts) != 2 or parts[0] != SECRET_PATH or not parts[1]:
            return not_found()
        target = parts[1]
    elif not path:
        # Без секрета корень не должен отзываться страницей Telegram (приманка для сканеров)
        return not_found()

    if not BOT_RE.match(target):
        return not_found()

    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in HOP_BY_HOP
    }

    try:
        upstream = session.request(
            method=request.method,
            url=f"{UPSTREAM}/{target}",
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
    return Response(upstream.iter_content(chunk_size=64 * 1024),
                    status=upstream.status_code, headers=resp_headers)


@app.before_request
def limit_body_size():
    if request.content_length and request.content_length > MAX_BODY_SIZE:
        return Response('{"ok": false, "error_code": 413, "description": "Request Entity Too Large"}',
                        status=413, mimetype="application/json")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
