#!/usr/bin/env bash
# OpenClaw Skill 一鍵安裝腳本
# 用法：
#   curl -fsSL https://raw.githubusercontent.com/fishbob889/openclaw-gomoku/main/install.sh | SKILL_TOKEN=xxx bash
#   或互動式：curl -fsSL ... | bash  （腳本會提示輸入 token）

set -e

INSTALL_DIR="$HOME/.openclaw-skill"
SKILL_JS_URL="https://raw.githubusercontent.com/fishbob889/openclaw-gomoku/main/dist/skill.js"
BIN_LINK="/usr/local/bin/openclaw-skill"

# ── 顏色輸出 ─────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[OpenClaw]${NC} $*"; }
success() { echo -e "${GREEN}✅${NC} $*"; }
warn()    { echo -e "${YELLOW}⚠️ ${NC} $*"; }
error()   { echo -e "${RED}❌${NC} $*"; exit 1; }

echo ""
echo -e "${CYAN}╔══════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   OpenClaw Gomoku Skill Installer    ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════╝${NC}"
echo ""

# ── 檢查 Node.js ─────────────────────────────────────────────
if ! command -v node &>/dev/null; then
  error "需要 Node.js 18+。請先安裝：https://nodejs.org"
fi

NODE_VER=$(node -e "process.stdout.write(process.version.slice(1))")
NODE_MAJOR=${NODE_VER%%.*}
if [ "$NODE_MAJOR" -lt 18 ]; then
  error "Node.js 版本過低（目前 v${NODE_VER}），需要 18+。"
fi
info "Node.js v${NODE_VER} ✓"

# ── 取得 Skill Token ──────────────────────────────────────────
if [ -z "$SKILL_TOKEN" ]; then
  echo ""
  echo -e "${YELLOW}請輸入你的 Skill Token${NC}（從 Telegram 傳 /skill 取得）："
  read -r SKILL_TOKEN
fi

if [ -z "$SKILL_TOKEN" ]; then
  error "未輸入 Skill Token。請先在 Telegram 傳 /register 完成聯盟註冊，再傳 /skill 取得安裝指令。"
fi

# ── 設定 API endpoint ─────────────────────────────────────────
OPENCLAW_API="${OPENCLAW_API:-https://fishbob-openclaw-api.fly.dev}"

# ── 建立安裝目錄 ──────────────────────────────────────────────
info "安裝目錄：${INSTALL_DIR}"
mkdir -p "$INSTALL_DIR"

# ── 下載 skill.js ─────────────────────────────────────────────
info "下載 skill.js …"
if command -v curl &>/dev/null; then
  curl -fsSL "$SKILL_JS_URL" -o "$INSTALL_DIR/skill.js"
elif command -v wget &>/dev/null; then
  wget -qO "$INSTALL_DIR/skill.js" "$SKILL_JS_URL"
else
  error "需要 curl 或 wget"
fi
success "skill.js 下載完成"

# ── 寫入設定檔 ────────────────────────────────────────────────
cat > "$INSTALL_DIR/skill.config.json" << CONFIG_EOF
{
  "skill_token": "${SKILL_TOKEN}"
}
CONFIG_EOF

# ── 寫入 .env ─────────────────────────────────────────────────
cat > "$INSTALL_DIR/.env" << ENV_EOF
API_BASE_URL=${OPENCLAW_API}
ENV_EOF

# ── 建立啟動腳本 ──────────────────────────────────────────────
cat > "$INSTALL_DIR/start.sh" << 'START_EOF'
#!/usr/bin/env bash
cd "$(dirname "$0")"
export $(grep -v '^#' .env | xargs) 2>/dev/null || true
node skill.js
START_EOF
chmod +x "$INSTALL_DIR/start.sh"

# ── 建立背景執行腳本 ──────────────────────────────────────────
cat > "$INSTALL_DIR/start-bg.sh" << 'BG_EOF'
#!/usr/bin/env bash
cd "$(dirname "$0")"
export $(grep -v '^#' .env | xargs) 2>/dev/null || true
LOG="$HOME/.openclaw-skill/skill.log"
nohup node skill.js >> "$LOG" 2>&1 &
echo $! > skill.pid
echo "✅ OpenClaw Skill 已在背景啟動（PID: $(cat skill.pid)）"
echo "📄 日誌：tail -f $LOG"
BG_EOF
chmod +x "$INSTALL_DIR/start-bg.sh"

# ── 建立停止腳本 ──────────────────────────────────────────────
cat > "$INSTALL_DIR/stop.sh" << 'STOP_EOF'
#!/usr/bin/env bash
PID_FILE="$(dirname "$0")/skill.pid"
if [ -f "$PID_FILE" ]; then
  kill "$(cat "$PID_FILE")" 2>/dev/null && echo "✅ OpenClaw Skill 已停止" || echo "進程已不存在"
  rm -f "$PID_FILE"
else
  echo "未找到 PID 檔案（Skill 可能未在背景執行）"
fi
STOP_EOF
chmod +x "$INSTALL_DIR/stop.sh"

# ── 嘗試建立全域指令 ─────────────────────────────────────────
if [ -w "/usr/local/bin" ] || sudo -n true 2>/dev/null; then
  sudo ln -sf "$INSTALL_DIR/start.sh" "$BIN_LINK" 2>/dev/null || true
  GLOBAL_CMD=true
fi

# ── 完成 ──────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║      安裝完成！                       ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
echo ""
success "安裝位置：${INSTALL_DIR}"
success "API 端點：${OPENCLAW_API}"
echo ""
echo -e "${CYAN}▶ 啟動 Skill（前景，看日誌）：${NC}"
echo "   ~/.openclaw-skill/start.sh"
echo ""
echo -e "${CYAN}▶ 背景執行：${NC}"
echo "   ~/.openclaw-skill/start-bg.sh"
echo ""
echo -e "${CYAN}▶ 停止背景 Skill：${NC}"
echo "   ~/.openclaw-skill/stop.sh"
echo ""
if [ "$GLOBAL_CMD" = true ]; then
  echo -e "${CYAN}▶ 全域指令（若有 sudo 權限）：${NC}"
  echo "   openclaw-skill"
  echo ""
fi
echo -e "${YELLOW}💡 提示：${NC}Skill 啟動後，在 Telegram 傳 /profile 確認 🟢 線上狀態"
echo ""
