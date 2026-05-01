import logging
from flask import Flask, request, jsonify, Response

from services.license_service import activate_license, check_license

logger = logging.getLogger(__name__)

_REQUIRED_ACTIVATE = {"api_key", "bot_username"}
_REQUIRED_CHECK    = {"api_key", "bot_username"}


def _missing_fields(data: dict, required: set) -> list[str]:
    return [f for f in required if not str(data.get(f, "")).strip()]


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False

    # ── Health check ──────────────────────────────────────────────────────────

    @app.route("/health", methods=["GET"])
    def health() -> Response:
        return jsonify({"ok": True, "status": "running"})

    # ── POST /api/license/activate ────────────────────────────────────────────

    @app.route("/api/license/activate", methods=["POST"])
    def license_activate() -> Response:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"ok": False, "message": "Request body must be valid JSON"}), 400

        missing = _missing_fields(data, _REQUIRED_ACTIVATE)
        if missing:
            return jsonify({"ok": False, "message": f"Missing fields: {', '.join(missing)}"}), 400

        result = activate_license(
            api_key=str(data["api_key"]).strip(),
            bot_username=str(data["bot_username"]).strip(),
            machine_id=str(data.get("machine_id", "") or "").strip() or None,
            server_ip=str(data.get("server_ip", "") or "").strip() or None,
        )
        status_code = 200 if result.get("ok") else 403
        logger.info(
            "activate | bot=%s owner_id=%s status=%s",
            data.get("bot_username"),
            data.get("owner_telegram_id"),
            result.get("status"),
        )
        return jsonify(result), status_code

    # ── POST /api/license/check ───────────────────────────────────────────────

    @app.route("/api/license/check", methods=["POST"])
    def license_check() -> Response:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"ok": False, "message": "Request body must be valid JSON"}), 400

        missing = _missing_fields(data, _REQUIRED_CHECK)
        if missing:
            return jsonify({"ok": False, "message": f"Missing fields: {', '.join(missing)}"}), 400

        result = check_license(
            api_key=str(data["api_key"]).strip(),
            bot_username=str(data["bot_username"]).strip(),
            machine_id=str(data.get("machine_id", "") or "").strip() or None,
        )
        logger.info(
            "check | bot=%s owner_id=%s licensed=%s",
            data.get("bot_username"),
            data.get("owner_telegram_id"),
            result.get("is_licensed"),
        )
        return jsonify(result), 200

    # ── 404 handler ───────────────────────────────────────────────────────────

    @app.errorhandler(404)
    def not_found(e) -> Response:
        return jsonify({"ok": False, "message": "Endpoint not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(e) -> Response:
        return jsonify({"ok": False, "message": "Method not allowed"}), 405

    return app
