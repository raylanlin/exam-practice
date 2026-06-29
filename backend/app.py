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

app = Flask(__name__, static_folder=None)
if CORS:
    CORS(app, resources={r"/api/*": {"origins": ALLOWED_ORIGIN}})


# --------------------------------------------------------------------------
# 认证
# --------------------------------------------------------------------------
def make_token(username):
    exp = int(time.time()) + TOKEN_TTL
    msg = "%s:%d" % (username, exp)
    sig = hmac.new(SECRET, msg.encode("utf-8"), hashlib.sha256).hexdigest()
    raw = "%s:%s" % (msg, sig)
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def verify_token(req):
    auth = req.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        raw = base64.urlsafe_b64decode(auth[7:].encode("ascii")).decode("utf-8")
        username, exp, sig = raw.rsplit(":", 2)
        msg = "%s:%s" % (username, exp)
        expected = hmac.new(SECRET, msg.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):   # 签名不符 → 伪造的 token
            return None
        if int(exp) < time.time():                    # 过期
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
        request.username = user
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
    ok = username in USERS and hmac.compare_digest(USERS[username], password)
    record_login(ip, ok)
    if not ok:
        return jsonify({"error": "账号或密码错误"}), 401
    return jsonify({"token": make_token(username), "username": username})


@app.route("/api/manifest")
@require_auth
def get_manifest():
    return jsonify({"version": 1, "exams": list_banks()})


@app.route("/api/exam/<exam_id>")
@require_auth
def get_exam(exam_id):
    path = find_bank_file(exam_id)
    if not path:
        return jsonify({"error": "找不到该题库"}), 404
    try:
        return jsonify(read_bank(path))
    except Exception as e:
        return jsonify({"error": "题库文件损坏：%s" % e}), 500


@app.route("/api/exam", methods=["POST"])
@require_auth
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
def delete_exam(exam_id):
    path = find_bank_file(exam_id)
    if not path:
        return jsonify({"error": "找不到该题库"}), 404
    os.remove(path)
    return ("", 204)


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
