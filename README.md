# 🎮☁️ Kerit-Renew
自动续期 Kerit 免费服务器，每 6 天定时运行。

> ⚠️ Kerit 官网会对访问 IP 进行验证，GitHub Actions 的出口 IP 无法直接通过，因此必须配置代理。

## 🔐 Secrets 配置
**Settings → Secrets and variables → Actions → New repository secret** 添加以下变量：

| Secret 名 | 必填 | 说明 | 示例 |
|---|---|---|---|
| `KERIT_ACCOUNT` | ✅ 必填 | 🧾 Kerit 登录邮箱和 Gmail 应用密码，用英文逗号分隔 | `example@gmail.com,abcdabcdabcdabcd` |
| `GOST_PROXY` | ✅ 必填 | 🌐 Gost 代理地址 | `socks5://user:pass@1.2.3.4:1080` |
| `TG_BOT` | 🔲 可选 | 📨 Telegram 推送，Chat ID 和 Bot Token 用英文逗号分隔 | `987654321,123456:AAFxxx` |

## 📝 Gmail 应用密码生成方式
Google 账号 → 安全性 → 两步验证（需先开启）→ 应用密码 → 选择"邮件" → 生成 → 将 16 位密码填入 Secret。
