#!/bin/bash
# ABA-Agent-Starter 一键部署脚本
# 在 GCP VM (Ubuntu 22.04) 的 SSH 终端中运行

set -e

echo "========================================="
echo "  ABA 临床督导系统 - 一键部署"
echo "========================================="

# 1. 系统依赖
echo "[1/7] 安装系统依赖..."
sudo apt update -y
sudo apt install -y python3-pip python3-venv git nginx redis-server

# 2. 克隆代码
echo "[2/7] 克隆代码..."
cd ~
if [ -d "ABA-Agent-Starter" ]; then
    cd ABA-Agent-Starter && git pull origin master
else
    git clone https://github.com/Jiamei-Zhang-BCBA/ABA-Agent-Starter.git
    cd ABA-Agent-Starter
fi

# 3. Python 虚拟环境 + 依赖
echo "[3/7] 安装 Python 依赖..."
cd ~/ABA-Agent-Starter/api
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 4. 创建 .env 配置
echo "[4/7] 创建配置文件..."
EXTERNAL_IP=$(curl -s http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip -H "Metadata-Flavor: Google")
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")

cat > ~/ABA-Agent-Starter/api/.env << ENVEOF
DATABASE_URL=sqlite+aiosqlite:///./aba_prod.db
REDIS_URL=redis://localhost:6379/0
STORAGE_MODE=local
LOCAL_STORAGE_PATH=./storage
JWT_SECRET_KEY=${JWT_SECRET}
CORS_ORIGINS=["http://localhost:3000","https://web-pi-five-39.vercel.app"]
CORS_ORIGIN_REGEX=https://.*\\.vercel\\.app
CLAUDE_MODE=cli
SKILLS_BASE_PATH=/root/ABA-Agent-Starter/.claude/skills
CLAUDE_MD_PATH=/root/ABA-Agent-Starter/CLAUDE.md
CONFIG_MD_PATH=/root/ABA-Agent-Starter/.claude/skills/_config.md
ENVEOF

echo "外部 IP: ${EXTERNAL_IP}"

# 5. 创建 systemd 服务
echo "[5/7] 创建系统服务..."
sudo tee /etc/systemd/system/aba-api.service > /dev/null << 'SERVICEEOF'
[Unit]
Description=ABA Clinical Supervision API
After=network.target redis.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/ABA-Agent-Starter/api
Environment=PATH=/root/ABA-Agent-Starter/api/venv/bin:/usr/bin:/bin
ExecStart=/root/ABA-Agent-Starter/api/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICEEOF

sudo systemctl daemon-reload
sudo systemctl enable aba-api
sudo systemctl start aba-api

# 6. 配置 Nginx 反向代理
echo "[6/7] 配置 Nginx..."
sudo tee /etc/nginx/sites-available/aba-api > /dev/null << 'NGINXEOF'
server {
    listen 80;
    server_name _;

    # API 代理
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE 支持
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400;
    }
}
NGINXEOF

sudo ln -sf /etc/nginx/sites-available/aba-api /etc/nginx/sites-enabled/aba-api
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

# 7. 设置每日自动备份
echo "[7/8] 设置每日备份..."
chmod +x ~/ABA-Agent-Starter/scripts/backup.sh
chmod +x ~/ABA-Agent-Starter/scripts/restore.sh
mkdir -p /root/backups/aba
# Add cron job if not already present
(crontab -l 2>/dev/null | grep -v "backup.sh"; echo "0 2 * * * /root/ABA-Agent-Starter/scripts/backup.sh >> /var/log/aba-backup.log 2>&1") | crontab -
echo "  每日凌晨2点自动备份，保留30天"

# 8. 验证
echo "[8/8] 验证部署..."
sleep 3
HEALTH=$(curl -s http://localhost:8000/health)
echo ""
echo "========================================="
echo "  部署完成！"
echo "========================================="
echo ""
echo "  后端 API: http://${EXTERNAL_IP}/api/v1"
echo "  健康检查: ${HEALTH}"
echo ""
echo "  管理命令:"
echo "    查看日志:   sudo journalctl -u aba-api -f"
echo "    重启服务:   sudo systemctl restart aba-api"
echo "    查看状态:   sudo systemctl status aba-api"
echo ""
echo "  下一步:"
echo "    1. 在 GCP 防火墙开放 HTTP (80) 端口"
echo "    2. 更新 Vercel 环境变量:"
echo "       NEXT_PUBLIC_API_URL=http://${EXTERNAL_IP}/api/v1"
echo "========================================="
