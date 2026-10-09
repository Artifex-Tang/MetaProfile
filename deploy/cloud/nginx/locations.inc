# MetaProfile 共享 location 块 —— 被 HTTP(80) 与 HTTPS(443) 两个 server 同时 include。
# 文件名用 .inc 而非 .conf:conf.d 下的 *.conf 会被 nginx 当成顶层配置自动加载。
#
# 关键:用变量 + resolver 运行时解析 backend 主机名,避免 backend 重建换 IP 后
# nginx 缓存旧 IP(启动时一次性解析)导致 502 Host unreachable。
resolver 127.0.0.11 valid=10s ipv6=off;

root /usr/share/nginx/html;
index index.html;

# 强制 UTF-8:无 charset 头时 CN-locale 浏览器会把 JS/JSON 按 GBK 解码 → 图谱中文标签 ???。
charset utf-8;
charset_types text/css text/plain text/xml application/javascript application/json image/svg+xml;

# SPA fallback
location / {
    try_files $uri $uri/ /index.html;
}

# 全部后端功能合并为单一 backend 容器(端口 8000),统一反代。
# 前缀 /api-xxx/ 被剥离后落到 backend 的 /api/v1 路由空间。
location ~ ^/api-(tech|project|org|person|scan|discovery|topic|settings)/ {
    set $upstream_backend http://backend:8000;
    rewrite ^/api-[^/]+/(.*)$ /$1 break;
    proxy_pass $upstream_backend;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Connection "";
    proxy_http_version 1.1;
}

# FastAPI swagger / redoc / openapi.json 反代(免对外开 8000)
location ~ ^/(docs|redoc|openapi\.json) {
    set $upstream_backend http://backend:8000;
    proxy_pass $upstream_backend;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
}

# MCP 服务(streamable HTTP,15 个只读工具)。
# SSE 长连接:必须关 proxy_buffering,否则响应被缓冲住,客户端一直收不到事件。
location /mcp {
    set $upstream_backend http://backend:8000;
    proxy_pass $upstream_backend;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
    chunked_transfer_encoding on;
}

gzip on;
gzip_types text/plain text/css application/javascript application/json;
gzip_min_length 1024;
