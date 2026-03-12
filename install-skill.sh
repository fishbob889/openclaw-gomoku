#!/usr/bin/env bash
# OpenClaw Gomoku Skill 安裝腳本
# 用法：curl -fsSL https://raw.githubusercontent.com/fishbob889/openclaw-gomoku/main/install-skill.sh | bash

set -e

SKILL_DIR="$HOME/.openclaw/skills/openclaw-gomoku"
SKILL_URL="https://raw.githubusercontent.com/fishbob889/openclaw-gomoku/main/SKILL.md"

CYAN='\033[0;36m'; GREEN='\033[0;32m'; NC='\033[0m'
info() { echo -e "${CYAN}[OpenClaw Gomoku]${NC} $*"; }
ok()   { echo -e "${GREEN}✅${NC} $*"; }

info "安裝 openclaw-gomoku Skill..."
mkdir -p "$SKILL_DIR"
curl -fsSL "$SKILL_URL" -o "$SKILL_DIR/SKILL.md"
ok "Skill 已安裝至 $SKILL_DIR/SKILL.md"
echo ""
echo "重啟 OpenClaw 後生效："
echo "  openclaw restart"
echo ""
echo "然後告訴你的 AI：register me on @ClawGomokuBot"
