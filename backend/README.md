# 考前刷题 · 后端部署说明

最简单、能直接跑通的方案：**Flask + 文件夹题库（json 文件）**。
题库就是一个文件夹里的一个个 `.json` 文件，格式和原来的 `data/*.json` 完全一样。

## 🔐 隐私与安全（务必先读）

开源仓库 + GitHub Pages 的前提下，**敏感内容绝不进仓库**，只存服务器：

| 内容 | 存哪 | 是否进公开仓库 |
|---|---|---|
| 前端 `index.html` | GitHub Pages | ✅ 公开（无任何密钥，只有一个 API 地址） |
| 后端**代码** `app.py` | 仓库 + 服务器 | ✅ 公开（不含账号密码） |
| **账号密码** | 服务器 `backend/users.json` | ❌ 已 .gitignore |
| **真实题库** `*.json` | 服务器 `backend/banks/` | ❌ 已 .gitignore（仅 `demo.json` 作样例） |

- 账号密码从服务器上的 `users.json`（或环境变量 `EXAM_USERS`）读取，**代码里没有真实密码**。
- 真实题库只上传到服务器的 `backend/banks/` 文件夹，不提交到仓库。
- 前端在 Pages 上是 https，后端**必须也用 https**（否则浏览器拦截混合内容），并把 `ALLOWED_ORIGIN` 限定到你的 Pages 域名。
- ⚠️ 如果此前已经把真实题库 / 密码提交过到公开仓库，它们仍留在 git 历史里：请**改掉密码**、并从历史中清除这些文件（`git filter-repo` 等）后再公开。

---

## 占位符（部署时替换）

| 占位符 | 含义 | 示例 |
|---|---|---|
| `<服务器IP>` | 你的阿里云公网 IP | `123.45.67.89` |
| `<域名或地址>` | 后端对外 https 地址 | `https://你的域名` 或 `https://<服务器IP>.sslip.io` |
| `<Pages地址>` | 前端 GitHub Pages 地址 | `https://你的用户名.github.io` |
| `<账号>/<密码>` | 登录账号 | 见服务器 `users.json` |

---

## 1. 配账号密码（只在服务器上）

拷贝模板改名，填上真实密码（此文件已 .gitignore，不会进仓库）：

```bash
cd backend
cp users.example.json users.json
# 编辑 users.json：
# { "student": "你的密码", "admin": "你的密码" }
```

> 或用环境变量：`export EXAM_USERS='{"student":"你的密码"}'`。
> 两者都没配时，仅本地会落到演示账号 `student/exam2026` 并打印警告——**别用于生产**。

## 2. 放题库

把题库 json 上传进服务器的 `backend/banks/` 文件夹，**一套题一个文件**，格式见仓库根目录 `README.md`。
（这些文件已 .gitignore，不进公开仓库；只有 `demo.json` 作为公开样例。）
登录后也能在网页「管理题库」里直接增删，会写到这个文件夹。

## 3. 跑起来（开发 / 试跑）

```bash
cd backend
pip install -r requirements.txt
python3 app.py
# 浏览器打开 http://<服务器IP>:5000
```

> 题库目录默认 `backend/banks`，前端目录默认仓库根目录（即上一级的 `index.html`）。
> 可用环境变量覆盖：`BANKS_DIR`、`FRONTEND_DIR`、`PORT`。

## 4. 配前端（GitHub Pages）

前端 `index.html` 顶部（`后端配置` 那段）把占位符 `YOUR_BACKEND_HOST` 换成你的后端 https 主机：

```js
var API_BASE = 'https://<你的后端地址>/exam-practice/api';   // 把 YOUR_BACKEND_HOST 换掉
var DEMO_MODE = false;                                       // 保持 false（预览/本地会自动走演示模式）
```

> ⚠️ **真实后端地址不要提交到公开源码仓库**：仓库里保留 `YOUR_BACKEND_HOST` 占位符，
> 发布到 Pages 时由部署脚本做一次替换（例如 `sed -i` 把 YOUR_BACKEND_HOST 换成真实主机）。
> （注：Pages 是直接拿文件当网站，发布后的那份前端中的地址浏览器能看到，这是 Pages 固有特性；此处只保证公开源码仓库不含它。）

> 同时在后端设 `ALLOWED_ORIGIN=<Pages地址>`（见第 5 步的 systemd `Environment`），
> 让 CORS 只放行你的前端域名。
> 如果改用「后端同时托管前端」（不用 Pages），则 `API_BASE='/api'` 即可（同源，无需 CORS，也不暴露任何地址）。

## 5. 生产常驻（systemd，推荐）

新建 `/etc/systemd/system/exam-practice.service`：

```ini
[Unit]
Description=Exam Practice API
After=network.target

[Service]
WorkingDirectory=/root/exam-practice/backend
ExecStart=/usr/bin/python3 /root/exam-practice/backend/app.py
Environment=PORT=5000
Environment=ALLOWED_ORIGIN=<Pages地址>
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable --now exam-practice
systemctl status exam-practice
```

阿里云安全组放行 5000 端口（或用下面的 Nginx 反代到 80/443）。

## 6.（可选）Nginx 反代 + HTTPS

```nginx
server {
    listen 80;
    server_name <域名或地址>;
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

HTTPS 可用 `certbot --nginx`，或临时用 `https://<服务器IP>.sslip.io` 这类免费泛解析。
此时前端 `API_BASE` 仍用 `'/api'` 即可（同源）。

---

## 🛡 服务器加固清单

代码已做的：token 用 HMAC 签名（防伪造）、登录失败限流（同 IP 10 次锁 5 分钟）、id 正则校验（防路径穿越）、密钥存服务器 `secret.key`（已 .gitignore）。下面是**你在服务器上要做的**：

1. **别用 Flask 自带服务器跑生产**，用 gunicorn：
   ```bash
   pip install gunicorn
   gunicorn -w 2 -b 127.0.0.1:5000 app:app
   ```
   只监听 `127.0.0.1`，由 Nginx 反代到外网（见第 6 节），不要把 5000 直接暴露公网。
2. **防火墙 / 安全组**：只放行 80、443、22；关掉 5000 的公网入站。
3. **HTTPS**：`certbot --nginx` 自动签证书；强制 http→https 跳转。
4. **非 root 运行**：建个普通用户跑服务（systemd 里 `User=exam`），别用 `/root`。
5. **SSH 加固**：仅密钥登录（`PasswordAuthentication no`）、禁 root 直登；装 `fail2ban` 挡暴力破解。
6. **文件权限**：`chmod 600 users.json secret.key`；题库目录别给其他用户写权限。
7. **保持更新**：`apt update && apt upgrade`，定期备份 `banks/` 和 `users.json`。
8. **密码**：明文存 `users.json` 够用但请设强密码；要更稳可改成哈希校验（werkzeug 的 `generate_password_hash` / `check_password_hash`）——需要的话我可以帮你改。

## API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/login` | `{username,password}` → `{token,username}` |
| GET | `/api/manifest` | 题库清单（扫描文件夹自动生成） |
| GET | `/api/exam/<id>` | 取某套题完整内容 |
| POST | `/api/exam` | 新增 / 覆盖题库（body=完整题库 json） |
| DELETE | `/api/exam/<id>` | 删除题库 |
| GET | `/api/health` | 健康检查 |

除 `/api/login` 和 `/api/health` 外，均需请求头 `Authorization: Bearer <token>`。
