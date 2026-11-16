import json

from flask import Blueprint, Response, current_app, jsonify

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.get("/rates")
def rates():
    resp = jsonify(current_app.rate_service.snapshot())
    resp.headers["Cache-Control"] = "no-store"
    return resp


@bp.get("/stream")
def stream():
    """Server-Sent Events: a snapshot on every change, plus one each refresh interval as a heartbeat."""
    svc, hub = current_app.rate_service, current_app.hub

    def events():
        while True:
            version = hub.version
            snap = svc.snapshot()
            yield f"data: {json.dumps(snap)}\n\n"
            hub.wait(version, snap["refresh_seconds"])

    return Response(events(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
