#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
考前刷题 · 后端 API（Flask）

设计要点（对应 CLAUDE.md / 用户需求）：
- 账号密码登录：账号写死在下面的 USERS 里（像参考仓库一样）。
- 题库 = 一个文件夹里的一个个 .json 文件，格式与现有 data/*.json 完全一致。
  manifest（题库清单）由后端扫描该文件夹自动生成，无需手工维护。
- 登录后可在网页里「增删题库」：POST/DELETE 直接写/删文件夹里的 json 文件。
- 同时托管前端 index.html（同源，无需跨域）；也开启了 CORS，方便前后端分开部署。

环境变量（可选，部署时按需设置）：
  BANKS_DIR    题库 json 文件夹      默认 ./banks
  FRONTEND_DIR 前端 index.html 目录  默认 仓库根目录（backend 的上一级）
  PORT         监听端口             默认 5000
"""

import os
import re
import json
import time
import hmac
import hashlib
import base64
from datetime import datetime
from functools import wraps

from flask import Flask, request, jsonify, send_from_directory, abort

try:
    from flask_cors import CORS
except Exception:  # flask_cors 未安装时不致命（同源托管也能用）
    CORS = None

# --------------------------------------------------------------------------
# 配置
# --------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BANKS_DIR = os.environ.get("BANKS_DIR", os.path.join(BASE_DIR, "banks"))
FRONTEND_DIR = os.environ.get("FRONTEND_DIR", os.path.dirname(BASE_DIR))
PORT = int(os.environ.get("PORT", "5000"))

# 允许跨域的前端来源：前端部署在 GitHub Pages 时，设为你的 Pages 地址，例如
#   ALLOWED_ORIGIN=https://<你的用户名>.github.io
# 默认 '*'（任意来源）仅供本地调试，生产请务必设成具体域名。
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "*")

# --------------------------------------------------------------------------
# 账号密码：绝不写死在代码里（代码会进公开仓库）。
# 从以下优先级加载，都只存在服务器上（均已 .gitignore）：
#   1) 环境变量 EXAM_USERS = '{"账号":"密码"}'
#   2) 服务器上的 backend/users.json（拷贝 users.example.json 改名而来）
#   3) 都没有时——仅本地调试的演示账号，并大声警告
# --------------------------------------------------------------------------
def load_users():
    env = os.environ.get("EXAM_USERS")
    if env:
        try:
            return json.loads(env)
        except Exception:
            print("⚠️  EXAM_USERS 不是合法 JSON，已忽略")
    users_file = os.environ.get("USERS_FILE", os.path.join(BASE_DIR, "users.json"))
    if os.path.isfile(users_file):
        try:
            with open(users_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print("⚠️  读取 users.json 失败：", e)
    print("⚠️  未找到 users.json / EXAM_USERS，使用演示账号 student/exam2026 —— 请勿用于生产！")
    return {"student": "exam2026"}

USERS = load_users()

# --------------------------------------------------------------------------
# 账号分级：users.json 里每个账号的值支持两种写法：
#   "raylan": "密码"                                    ← 旧写法，视为 admin（自用）
#   "buyer_tom": {"password": "密码", "role": "buyer",
#                 "banks": ["gdufe-xxx"],                 ← 只能看这些题库
#                 "expires": "2026-09-01"}                ← 可选，到期无法登录/使用
# 角色能力：
#   admin —— 全部题库、可增删题库、不受单设备限制（多设备同时在线）
#   buyer —— 仅 banks 列表内题库、不可增删、单设备（新登录踢掉旧设备）
# 权限在服务端每次请求时查，改 users.json + 重启即时生效。
# --------------------------------------------------------------------------
def account(username):
    """返回规范化账号信息 dict，或 None。"""
    v = USERS.get(username)
    if v is None:
        return None
    if isinstance(v, str):
        return {"password": v, "role": "admin", "banks": None, "expires": None}
    if isinstance(v, dict) and isinstance(v.get("password"), str):
        role = v.get("role", "buyer")
        if role not in ("admin", "buyer"):
            role = "buyer"
        banks = v.get("banks")
        if not isinstance(banks, list):
            banks = [] if role == "buyer" else None
        return {"password": v["password"], "role": role,
                "banks": None if role == "admin" else banks,
                "expires": v.get("expires") or None}
    return None


def account_expired(acc):
    if not acc or not acc.get("expires"):
        return False
    try:
        return datetime.utcnow().date().isoformat() > str(acc["expires"])
    except Exception:
        return False


def bank_allowed(acc, exam_id):
    if acc["role"] == "admin" or acc["banks"] is None:
        return True
    return exam_id in acc["banks"]

# 签名密钥：用于给 token 签名（防伪造）。优先环境变量 SECRET_KEY，
# 否则读/生成 backend/secret.key（已 .gitignore，只存服务器）。
def load_secret():
    s = os.environ.get("SECRET_KEY")
    if s:
        return s.encode("utf-8")
    path = os.path.join(BASE_DIR, "secret.key")
    if os.path.isfile(path):
        with open(path, "rb") as f:
            return f.read().strip()
    key = base64.urlsafe_b64encode(os.urandom(32))
    try:
        with open(path, "wb") as f:
            f.write(key)
        os.chmod(path, 0o600)
    except Exception as e:
        print("⚠️  无法写入 secret.key，本次使用临时密钥（重启后登录会失效）：", e)
    return key

SECRET = load_secret()

TOKEN_TTL = 60 * 60 * 24 * 30  # 登录有效期 30 天（秒）
ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")

os.makedirs(BANKS_DIR, exist_ok=True)

# --------------------------------------------------------------------------
# 激活码（发行单文件给买家用）：存在 backend/codes.json，结构：
#   { "<码>": {"bank":"<题库id>", "note":"备注", "device":null或设备id,
#              "expires":"YYYY-MM-DD"或null, "revoked":false} }
# 单个码同时只绑定 1 个设备：用同一码在新设备激活会把旧设备踢下线（同买家账号逻辑）。
# --------------------------------------------------------------------------
CODES_FILE = os.environ.get("CODES_FILE", os.path.join(BASE_DIR, "codes.json"))
_codes_lock_placeholder = None


def load_codes():
    if os.path.isfile(CODES_FILE):
        try:
            with open(CODES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_codes(codes):
    with open(CODES_FILE, "w", encoding="utf-8") as f:
        json.dump(codes, f, ensure_ascii=False, indent=2)


def gen_code():
    import random, string
    alphabet = string.ascii_uppercase.replace("O", "").replace("I", "") + string.digits
    return "-".join("".join(random.choice(alphabet) for _ in range(4)) for _ in range(2))


def make_license(code, device_id, bank, exp):
    msg = "lic:%s:%s:%s:%d" % (code, device_id, bank, exp)
    sig = hmac.new(SECRET, msg.encode("utf-8"), hashlib.sha256).hexdigest()
    raw = "%s:%s" % (msg, sig)
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def verify_license(token):
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
        sig = raw.rsplit(":", 1)[-1]
        msg_body = raw.rsplit(":", 1)[0]
        expected = hmac.new(SECRET, msg_body.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        _, code, device_id, bank, exp = msg_body.split(":")
        if int(exp) < time.time():
            return None
        return {"code": code, "device_id": device_id, "bank": bank}
    except Exception:
        return None

app = Flask(__name__, static_folder=None)
if CORS:
    CORS(app, resources={r"/api/*": {"origins": ALLOWED_ORIGIN}})


# --------------------------------------------------------------------------
# 认证
# --------------------------------------------------------------------------
def make_token(username):
    exp = int(time.time()) + TOKEN_TTL
    ns = time.time_ns()  # 纳秒精度，确保同一秒多账号登录 token 不重复
    msg = "%s:%d:%d" % (username, exp, ns)
    sig = hmac.new(SECRET, msg.encode("utf-8"), hashlib.sha256).hexdigest()
    raw = "%s:%s" % (msg, sig)
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def verify_token(req):
    auth = req.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        raw = base64.urlsafe_b64decode(auth[7:].encode("ascii")).decode("utf-8")
        # 格式: username:exp[:nonce]:sig → 切最后一个冒号取签名
        sig = raw.rsplit(":", 1)[-1]
        msg_body = raw.rsplit(":", 1)[0]  # "username:exp:nonce"
        expected = hmac.new(SECRET, msg_body.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):   # 签名不符 → 伪造的 token
            return None
        # msg_body = "username:exp"（旧格式）或 "username:exp:nonce"（新格式）
        parts = msg_body.split(":")
        if len(parts) < 2:
            return None
        username, exp_str = parts[0], parts[1]
        if int(exp_str) < time.time():                # 过期
            return None
        if username not in USERS:
            return None
        return username
    except Exception:
        return None


def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = verify_token(request)
        if not user:
            return jsonify({"error": "未授权或登录已过期"}), 401
        acc = account(user)
        if not acc:
            return jsonify({"error": "账号不存在"}), 401
        if account_expired(acc):
            return jsonify({"error": "账号已到期，请联系管理员续费"}), 401
        request.username = user
        request.account = acc
        return fn(*args, **kwargs)
    return wrapper


def require_admin(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if getattr(request, "account", {}).get("role") != "admin":
            return jsonify({"error": "无权限：仅管理账号可操作题库"}), 403
        return fn(*args, **kwargs)
    return wrapper


# --------------------------------------------------------------------------
# 题库（文件夹里的 json 文件）
# --------------------------------------------------------------------------
def safe_id(exam_id):
    return bool(exam_id) and bool(ID_RE.match(exam_id))


def bank_path(exam_id):
    return os.path.join(BANKS_DIR, exam_id + ".json")


def read_bank(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_banks():
    """扫描题库文件夹，返回 manifest 风格的清单（含真实题数）。"""
    exams = []
    for name in sorted(os.listdir(BANKS_DIR)):
        if not name.endswith(".json") or name == "manifest.json":
            continue
        path = os.path.join(BANKS_DIR, name)
        try:
            data = read_bank(path)
        except Exception:
            continue
        exam_id = data.get("id") or name[:-5]
        exams.append({
            "id": exam_id,
            "file": name,
            "title": data.get("title", exam_id),
            "subject": data.get("subject", ""),
            "examDate": data.get("examDate", ""),
            "duration": data.get("duration", 0),
            "questionCount": len(data.get("questions", []) or []),
            "description": data.get("description", ""),
        })
    return exams


def find_bank_file(exam_id):
    """按 id 找文件：优先 <id>.json，否则扫描每个文件的内部 id。"""
    direct = bank_path(exam_id)
    if os.path.isfile(direct):
        return direct
    for name in os.listdir(BANKS_DIR):
        if not name.endswith(".json") or name == "manifest.json":
            continue
        path = os.path.join(BANKS_DIR, name)
        try:
            if read_bank(path).get("id") == exam_id:
                return path
        except Exception:
            continue
    return None


def validate_bank(data):
    if not isinstance(data, dict):
        return "题库必须是 JSON 对象"
    if not safe_id(data.get("id")):
        return "缺少合法 id（只能含字母、数字、- 和 _）"
    if not data.get("title"):
        return "缺少 title"
    qs = data.get("questions")
    if not isinstance(qs, list) or not qs:
        return "questions 不能为空"
    return None


# --------------------------------------------------------------------------
# API 路由
# --------------------------------------------------------------------------
@app.route("/api/health")
def health():
    return jsonify({"status": "healthy", "banks": len(list_banks())})


# 登录限流：同一 IP 连续失败 10 次后锁 5 分钟（防暴力破解）
_login_fails = {}
_active_tokens = {}  # username -> current_active_token 字符串


def login_locked(ip):
    rec = _login_fails.get(ip)
    return bool(rec and rec[0] >= 10 and time.time() - rec[1] < 300)


def record_login(ip, ok):
    if ok:
        _login_fails.pop(ip, None)
        return
    now = time.time()
    rec = _login_fails.get(ip)
    if not rec or now - rec[1] >= 300:
        _login_fails[ip] = [1, now]
    else:
        rec[0] += 1


@app.route("/api/login", methods=["POST"])
def login():
    ip = request.headers.get("X-Real-IP") or request.remote_addr or "?"
    if login_locked(ip):
        return jsonify({"error": "尝试过于频繁，请 5 分钟后再试"}), 429
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    acc = account(username)
    ok = bool(acc) and hmac.compare_digest(acc["password"], password)
    record_login(ip, ok)
    if not ok:
        return jsonify({"error": "账号或密码错误"}), 401
    if account_expired(acc):
        return jsonify({"error": "账号已到期，请联系管理员续费"}), 401

    token = make_token(username)
    resp = {"token": token, "username": username, "role": acc["role"]}
    # 单设备限制只针对 buyer；admin（自用）不占 slot、不踢旧设备
    if acc["role"] != "admin":
        if username in _active_tokens:
            resp["kicked_old_device"] = True
        _active_tokens[username] = token
    return jsonify(resp)


@app.route("/api/manifest")
@require_auth
def get_manifest():
    acc = request.account
    exams = [e for e in list_banks() if bank_allowed(acc, e["id"])]
    return jsonify({"version": 1, "exams": exams, "role": acc["role"]})


@app.route("/api/refresh", methods=["POST"])
@require_auth
def refresh_token():
    """用旧 token 换新 token。buyer 只有当前活跃 slot 里的 token 能换；
    admin 不受单设备限制，任何有效 token 都能换。"""
    user = request.username
    acc = request.account
    if acc["role"] != "admin":
        auth = request.headers.get("Authorization", "")
        token_str = auth[7:] if auth.startswith("Bearer ") else ""
        if _active_tokens.get(user) != token_str:
            return jsonify({"error": "账号已在其他设备登录，请重新登录"}), 401
        new_token = make_token(user)
        _active_tokens[user] = new_token
    else:
        new_token = make_token(user)
    return jsonify({"token": new_token, "role": acc["role"]})


@app.route("/api/exam/<exam_id>")
@require_auth
def get_exam(exam_id):
    if not bank_allowed(request.account, exam_id):
        return jsonify({"error": "无权限访问该题库"}), 403
    path = find_bank_file(exam_id)
    if not path:
        return jsonify({"error": "找不到该题库"}), 404
    try:
        return jsonify(read_bank(path))
    except Exception as e:
        return jsonify({"error": "题库文件损坏：%s" % e}), 500


@app.route("/api/exam", methods=["POST"])
@require_auth
@require_admin
def save_exam():
    data = request.get_json(silent=True) or {}
    err = validate_bank(data)
    if err:
        return jsonify({"error": err}), 400
    data["updatedAt"] = datetime.utcnow().isoformat()
    with open(bank_path(data["id"]), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return jsonify({"status": "ok", "id": data["id"]})


@app.route("/api/exam/<exam_id>", methods=["DELETE"])
@require_auth
@require_admin
def delete_exam(exam_id):
    path = find_bank_file(exam_id)
    if not path:
        return jsonify({"error": "找不到该题库"}), 404
    os.remove(path)
    return ("", 204)


# --------------------------------------------------------------------------
# 激活码（管理 = admin。激活/心跳 = 公开，供发行的单文件调用，不需 Bearer token）
# --------------------------------------------------------------------------
@app.route("/api/codes", methods=["GET"])
@require_auth
@require_admin
def list_codes():
    bank = request.args.get("bank")
    codes = load_codes()
    out = []
    for c, v in codes.items():
        if bank and v.get("bank") != bank:
            continue
        out.append(dict(v, code=c))
    return jsonify({"codes": out})


@app.route("/api/codes", methods=["POST"])
@require_auth
@require_admin
def create_code():
    data = request.get_json(silent=True) or {}
    bank = data.get("bank")
    if not safe_id(bank) or not find_bank_file(bank):
        return jsonify({"error": "题库 id 无效"}), 400
    codes = load_codes()
    code = data.get("code") or gen_code()
    while code in codes:
        code = gen_code()
    codes[code] = {
        "bank": bank,
        "note": (data.get("note") or "").strip()[:100],
        "device": None,
        "expires": data.get("expires") or None,
        "revoked": False,
    }
    save_codes(codes)
    return jsonify(dict(codes[code], code=code))


@app.route("/api/codes/<code>", methods=["DELETE"])
@require_auth
@require_admin
def revoke_code(code):
    codes = load_codes()
    if code not in codes:
        return jsonify({"error": "激活码不存在"}), 404
    codes[code]["revoked"] = True
    save_codes(codes)
    return jsonify({"status": "ok"})


@app.route("/api/codes/<code>/reset", methods=["POST"])
@require_auth
@require_admin
def reset_code(code):
    """清除设备绑定，让买家换设备时无需踢人就能重新激活（或用于遗失设备后重置）。"""
    codes = load_codes()
    if code not in codes:
        return jsonify({"error": "激活码不存在"}), 404
    codes[code]["device"] = None
    save_codes(codes)
    return jsonify({"status": "ok"})


def _code_state(v):
    if v.get("revoked"):
        return "revoked"
    if v.get("expires") and datetime.utcnow().date().isoformat() > str(v["expires"]):
        return "expired"
    return "ok"


@app.route("/api/license/activate", methods=["POST"])
def license_activate():
    """买家发行包首次激活（或换设备重激活）。无需登录账号，只需激活码 + 本机生成的设备 id。"""
    ip = request.headers.get("X-Real-IP") or request.remote_addr or "?"
    if login_locked(ip):
        return jsonify({"error": "尝试过于频繁，请 5 分钟后再试"}), 429
    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip().upper()
    device_id = (data.get("device_id") or "").strip()
    if not code or not device_id:
        return jsonify({"error": "缺少激活码或设备标识"}), 400
    codes = load_codes()
    v = codes.get(code)
    record_login(ip, bool(v))
    if not v:
        return jsonify({"error": "激活码不存在"}), 404
    state = _code_state(v)
    if state == "revoked":
        return jsonify({"error": "激活码已被吐销"}), 403
    if state == "expired":
        return jsonify({"error": "激活码已过期"}), 403
    path = find_bank_file(v["bank"])
    if not path:
        return jsonify({"error": "对应题库不存在"}), 404
    kicked = v.get("device") and v["device"] != device_id
    v["device"] = device_id
    save_codes(codes)
    exp = int(time.time()) + TOKEN_TTL
    token = make_license(code, device_id, v["bank"], exp)
    resp = {"license": token, "exam": read_bank(path)}
    if kicked:
        resp["kicked_old_device"] = True
    return jsonify(resp)


@app.route("/api/license/heartbeat", methods=["POST"])
def license_heartbeat():
    """发行包定期心跳：确认本设备仍是该码当前绑定的设备（否则说明被其他设备重新激活踢下线了）。"""
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    lic = verify_license(token)
    if not lic:
        return jsonify({"ok": False, "error": "授权已失效"}), 401
    data = request.get_json(silent=True) or {}
    device_id = (data.get("device_id") or "").strip()
    codes = load_codes()
    v = codes.get(lic["code"])
    if not v or _code_state(v) != "ok" or v.get("device") != device_id or lic["device_id"] != device_id:
        return jsonify({"ok": False, "error": "已在其他设备激活，本设备已失效"}), 409
    return jsonify({"ok": True})


# --------------------------------------------------------------------------
# 托管前端（同源，免跨域）
# --------------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:path>")
def static_files(path):
    if path.startswith("api/"):
        abort(404)
    full = os.path.join(FRONTEND_DIR, path)
    if os.path.isfile(full):
        return send_from_directory(FRONTEND_DIR, path)
    # 单页应用回退：未知路径返回首页
    return send_from_directory(FRONTEND_DIR, "index.html")


if __name__ == "__main__":
    print("题库目录 BANKS_DIR =", BANKS_DIR)
    print("前端目录 FRONTEND_DIR =", FRONTEND_DIR)
    print("监听端口 PORT =", PORT)
    app.run(host="0.0.0.0", port=PORT, debug=False)
