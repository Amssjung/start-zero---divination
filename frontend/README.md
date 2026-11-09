# 前端

## 现状

前端是一个**单文件 HTML**（约 4.6 MB），把界面、路由、请求、样式全部打包在一起。
没有构建产物目录之外的源码交付，因此本仓库**不包含**这个文件。

## 为什么不在仓库里

- 体积大（4.6 MB），每次重新构建都会产生大 diff，污染提交历史
- 它是合作方维护的产物，不是本仓库的代码
- 二进制式的一个文件，代码审查没有意义

## 它做了什么

| 模块 | 作用 |
| --- | --- |
| 起盘 | 抽牌、摇卦、算星座等在前端完成 |
| 请求 Dify | `POST /v1/chat-messages`，把盘面交给对话流换回解读 |
| 登录注册 | `POST /api/auth/login`、`/api/auth/register`，拿 token |
| 历史 | `GET/POST /api/history`，带 `Authorization: Bearer <token>` |
| 本地缓存 | 登录态与历史列表存 localStorage，加速首屏 |

## 对接后端需要的约定

```
API Base URL       http://<后端地址>:8000
Authorization      Bearer <登录返回的 token>
POST /api/auth/login     {username, password}   → {ok, token, user}
POST /api/auth/register  {username, display_name, password} → 同上
GET  /api/history        → {ok, data: [...]}
POST /api/history        {question, method, hexagram, result} → {ok, reading}
```

`user` 对象用驼峰命名：`{username, displayName, createdAt}`。
登录失败统一返回 `{ok: false, error: "中文提示"}`。

## 如果你想自己写一个前端

后端只认 HTTP + JSON，任何技术栈都可以对接。最小可用界面需要：

1. 一个输入框（问什么）
2. 一次 Dify 调用（拿解读）
3. 一次 `/api/history` 调用（存记录）
4. 一个历史列表（读记录）
