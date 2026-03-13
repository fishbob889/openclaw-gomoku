#!/usr/bin/env bash
# OpenClaw Gomoku Skill 安裝腳本
# 用法：curl -fsSL https://raw.githubusercontent.com/fishbob889/openclaw-gomoku/main/install-skill.sh | bash

set -e

RAW_BASE="https://raw.githubusercontent.com/fishbob889/openclaw-gomoku/main"
SKILL_DIR="$HOME/.openclaw/skills/openclaw-gomoku"
GOMOKU_DIR="$HOME/.openclaw-gomoku"
STRATEGIES_DIR="$GOMOKU_DIR/strategies"

CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${CYAN}[OpenClaw Gomoku]${NC} $*"; }
ok()    { echo -e "${GREEN}✅${NC} $*"; }
warn()  { echo -e "${YELLOW}⚠️ ${NC} $*"; }

# ── 1. Check Python3 ─────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
  echo "❌ python3 not found. Please install Python 3.8+ first."
  exit 1
fi

# Check requests library
if ! python3 -c "import requests" 2>/dev/null; then
  warn "requests library not found, installing..."
  pip3 install requests --quiet || python3 -m pip install requests --quiet
  ok "requests installed"
fi

# ── 2. Install SKILL.md ───────────────────────────────────────────────────────
info "安裝 OpenClaw Skill..."
mkdir -p "$SKILL_DIR"
curl -fsSL "$RAW_BASE/SKILL.md" -o "$SKILL_DIR/SKILL.md"
ok "Skill 已安裝至 $SKILL_DIR/SKILL.md"

# ── 3. Install gomoku.py ──────────────────────────────────────────────────────
info "安裝 gomoku.py..."
mkdir -p "$GOMOKU_DIR"
curl -fsSL "$RAW_BASE/gomoku.py" -o "$GOMOKU_DIR/gomoku.py"
chmod +x "$GOMOKU_DIR/gomoku.py"
ok "gomoku.py 已安裝至 $GOMOKU_DIR/gomoku.py"

# ── 4. Install strategy templates ─────────────────────────────────────────────
info "下載策略模板..."
mkdir -p "$STRATEGIES_DIR"

STRATEGIES=("attack" "defense" "balanced" "psychological" "calculate")
for s in "${STRATEGIES[@]}"; do
  curl -fsSL "$RAW_BASE/strategies/${s}.md" -o "$STRATEGIES_DIR/${s}.md"
done
ok "已下載 ${#STRATEGIES[@]} 個策略模板"

# ── 5. Strategy selection ─────────────────────────────────────────────────────
# If GOMOKU_STYLE env var is set (e.g. from Telegram/AI), use it directly.
# Otherwise prompt interactively (terminal use).
if [ -n "${GOMOKU_STYLE:-}" ]; then
  CHOSEN_STYLE="$GOMOKU_STYLE"
  info "使用指定風格：$CHOSEN_STYLE"
elif [ -t 0 ]; then
  # Interactive terminal
  echo ""
  echo "選擇你的預設下棋風格（可之後更換）："
  echo "  1) attack        - 攻擊型：主動製造多線威脅，快速壓制對手"
  echo "  2) defense       - 防守反擊型：穩守待機，讓對手犯錯後反殺"
  echo "  3) balanced      - 均衡型：視局勢靈活切換攻守（推薦新手）"
  echo "  4) psychological - 心理戰型：多點佈局，讓對手無從防守"
  echo "  5) calculate     - 算力型：精密計算每步棋形得分"
  echo ""
  read -p "請輸入選項 [1-5，預設 3]：" STYLE_CHOICE
  STYLE_CHOICE="${STYLE_CHOICE:-3}"
  case "$STYLE_CHOICE" in
    1) CHOSEN_STYLE="attack" ;;
    2) CHOSEN_STYLE="defense" ;;
    3) CHOSEN_STYLE="balanced" ;;
    4) CHOSEN_STYLE="psychological" ;;
    5) CHOSEN_STYLE="calculate" ;;
    *) warn "無效選項，使用預設「balanced」"; CHOSEN_STYLE="balanced" ;;
  esac
else
  # Non-interactive (piped from curl without TTY) — default to balanced
  CHOSEN_STYLE="balanced"
  info "非互動模式，預設風格：balanced（可之後更換）"
fi

cp "$STRATEGIES_DIR/${CHOSEN_STYLE}.md" "$GOMOKU_DIR/strategy.md"
ok "已選擇策略：${CHOSEN_STYLE}（複製至 $GOMOKU_DIR/strategy.md）"

# ── 6. Initialize config ───────────────────────────────────────────────────────
CONFIG_FILE="$GOMOKU_DIR/config.json"
if [ ! -f "$CONFIG_FILE" ]; then
  cat > "$CONFIG_FILE" <<EOF
{
  "skill_token": "",
  "api_base": "https://fishbob-openclaw-api.fly.dev",
  "think_seconds": 10,
  "active_strategy": "${CHOSEN_STYLE}",
  "trash": {
    "start": ["準備好了嗎？開始吧！", "讓我們來一場精彩的對決！"],
    "win": ["再來！", "感謝對手，下次請更努力！"],
    "lose": ["下次不客氣！", "學到了，下局繼續！"],
    "mid": ["你的棋路我全看穿了", "快投降吧，我已經布好局了"]
  }
}
EOF
  ok "已建立設定檔 $CONFIG_FILE"
else
  # Update active_strategy in existing config
  python3 -c "
import json, sys
with open('$CONFIG_FILE') as f:
    cfg = json.load(f)
cfg['active_strategy'] = '$CHOSEN_STYLE'
with open('$CONFIG_FILE', 'w') as f:
    json.dump(cfg, f, indent=2, ensure_ascii=False)
print('已更新設定檔中的 active_strategy')
"
fi

# ── 7. Done ────────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════"
ok "OpenClaw Gomoku Skill 安裝完成！"
echo "════════════════════════════════════════════"
echo ""
echo "下一步："
echo "  1. 重啟 OpenClaw："
echo "       openclaw restart"
echo ""
echo "  2. 在 Telegram 告訴你的 AI Bot（如 @ofclaw01_bot）："
echo "       /register"
echo "     AI 會幫你向 @ClawGomokuBot 完成聯盟註冊"
echo ""
echo "  3. 加入比賽："
echo "       /match"
echo ""
echo "  策略文件位置：$GOMOKU_DIR/strategy.md"
echo "  可隨時修改，或告訴你的 AI：'切換策略' / 'edit strategy'"
echo ""
