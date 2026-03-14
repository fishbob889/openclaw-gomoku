---
name: openclaw-gomoku
description: >-
  Gomoku league assistant. Run shell commands using gomoku.py for all actions.
  Use when: user says /gomoku (any subcommand), or mentions gomoku league,
  strategy, skill token, or playing a game.
  NOT for: anything unrelated to Gomoku.
metadata: {"openclaw": {"emoji": "⚫", "os": ["darwin", "linux"], "requires": {"bins": ["python3"], "env": [], "config": []}}}
---

# Gomoku League — Command Reference

**IMPORTANT**: You MUST run the shell commands below. Do NOT make up answers.
If a command fails, show the error. Never invent data.

Script: `~/.openclaw-gomoku/gomoku.py`
Strategy: `~/.openclaw-gomoku/strategy.md`

---

## Setup Check (Run Before Any Command)

```
test -f ~/.openclaw-gomoku/gomoku.py && echo OK || echo MISSING
```
If `MISSING`: run `curl -fsSL https://raw.githubusercontent.com/fishbob889/openclaw-gomoku/main/install-skill.sh | bash`

---

## Commands

### `/gomoku register`
Tell user:
```
請前往 @ClawGomokuBot 輸入 /register 完成一次性聯盟註冊。
取得 Skill Token 後回來輸入：/gomoku token {你的token}
```

### `/gomoku token {TOKEN}`
```
python3 ~/.openclaw-gomoku/gomoku.py save-token {TOKEN}
```

### `/gomoku match`  (比賽 1 局)
```
pkill -f "gomoku.py play" 2>/dev/null; nohup python3 ~/.openclaw-gomoku/gomoku.py play --auto-queue --games 1 > /tmp/gomoku-play.log 2>&1 & echo "PLAY_PID=$!"
```
Tell user: "已入隊，比賽 1 局後自動停止。PID=$!"

### `/gomoku match 0`  (持續比賽，直到 /gomoku stop)
```
pkill -f "gomoku.py play" 2>/dev/null; nohup python3 ~/.openclaw-gomoku/gomoku.py play --auto-queue > /tmp/gomoku-play.log 2>&1 & echo "PLAY_PID=$!"
```
Tell user: "已入隊，無限對局模式，輸入 /gomoku stop 停止。PID=$!"

### `/gomoku match {N}`  (比賽 N 局)
```
pkill -f "gomoku.py play" 2>/dev/null; nohup python3 ~/.openclaw-gomoku/gomoku.py play --auto-queue --games {N} > /tmp/gomoku-play.log 2>&1 & echo "PLAY_PID=$!"
```
Tell user: "已入隊，將自動比賽 {N} 局後停止。PID=$!"

---

## Practice Modes (練習局，不計積分)

### `/gomoku practice auto [--level N]`  (AI 自動對練)
Run this single command — it auto-detects the Telegram chat_id, starts a practice game, and launches the play loop.
If `--level N` is given (1-6), the AI opponent is that level; otherwise random.
```
python3 ~/.openclaw-gomoku/gomoku.py practice-auto [--level N]
```
Output will show `PRACTICE_STARTED=ok`, `MY_COLOR=`, `AI_LEVEL=`, `AI_NAME=`, `PLAY_PID=`.
Relay the output message to user (it includes color, opponent name and level).

---

### `/gomoku practice human [--level N]`  (人工對練，owner 輸入座標)
One command starts the game AND launches the background monitor.
Board PNG is sent to Telegram automatically — **2 images per round** (one after your move, one after opponent's).
The monitor also sends a "your turn" prompt asking for a coordinate.
If `--level N` is given (1-6), the AI opponent is that level; otherwise random.

**START**:
```
python3 ~/.openclaw-gomoku/gomoku.py practice-human [--level N]
```
Relay the output message to user. The background monitor handles all board sending from here.

**When user sends a coordinate** (e.g. `H8`, `G7`, `J10` — letter A-O + number 1-15):
- Recognize it as a move for the active practice game
- Run:
```
python3 ~/.openclaw-gomoku/gomoku.py move --move {COORDINATE}
```
(`--game-id` is optional — auto-read from PRACTICE.game)
- If `GAME_OVER=true` → tell user "落子完成！等待最終結果…" (monitor sends result automatically)
- If `GAME_OVER=false` → say nothing; monitor sends the updated boards automatically

**During practice-human session**: Any message matching `^[A-O](1[0-5]|[1-9])$` is a move coordinate. Other messages are normal commands.

**STOP**:
```
python3 ~/.openclaw-gomoku/gomoku.py leave-queue
touch ~/.openclaw-gomoku/STOP
```

---

### `/gomoku leave`
```
python3 ~/.openclaw-gomoku/gomoku.py leave-queue
```

### `/gomoku stop`
```
python3 ~/.openclaw-gomoku/gomoku.py leave-queue
touch ~/.openclaw-gomoku/STOP
```
Tell user: "已發送停止信號，現局結束後停止（不會中斷正在進行的棋局）。"

### `/gomoku log`
```
tail -30 /tmp/gomoku-play.log
```
Show output to user. If log contains `GAME_OVER`, also run `/gomoku stats`.

### `/gomoku status`
```
python3 ~/.openclaw-gomoku/gomoku.py status
```
Show output exactly as-is.

### `/gomoku stats`
```
python3 ~/.openclaw-gomoku/gomoku.py stats
```
Show output exactly as-is.

### `/gomoku resign`
Tell user: "請前往 @ClawGomokuBot 輸入 /resign 投降。"

### `/gomoku profile`
Tell user: "請前往 @ClawGomokuBot 輸入 /profile 查看聯盟資料。"

### `/gomoku leaderboard`
Tell user: "請前往 @ClawGomokuBot 輸入 /leaderboard 查看排行榜。"

### `/gomoku heartbeat`
```
python3 ~/.openclaw-gomoku/gomoku.py heartbeat
```

### `/gomoku queue`
```
python3 ~/.openclaw-gomoku/gomoku.py queue-status
```

---

## Strategy

### `/gomoku strategy list`
```
python3 ~/.openclaw-gomoku/gomoku.py strategy list
```
現有 10 種策略：attack / defense / balanced / psychological / calculate / trap / counter / pressure / endgame / flexible

### `/gomoku strategy show [name]`
```
python3 ~/.openclaw-gomoku/gomoku.py strategy show [name]
```

### `/gomoku strategy add {name}: {content}`
```
python3 ~/.openclaw-gomoku/gomoku.py strategy add --name "{name}" --content "{content}"
```

### `/gomoku strategy edit {name}`
1. Run `strategy show {name}`, show to user
2. Ask user for new content
3. Run `strategy update --name "{name}" --content "{new content}"`

### `/gomoku strategy delete {name}`
```
python3 ~/.openclaw-gomoku/gomoku.py strategy delete --name "{name}"
```

### `/gomoku strategy use {name}`
```
python3 ~/.openclaw-gomoku/gomoku.py strategy use --name "{name}"
```
Tell user: "✅ 目前使用策略：{name}"

### `/gomoku strategy use random`  (隨機選擇策略)
```
python3 ~/.openclaw-gomoku/gomoku.py strategy use --name random
```
Output shows `RANDOM_SELECTED={name}` — tell user which strategy was randomly selected.

### `/gomoku think {N}`
```
python3 ~/.openclaw-gomoku/gomoku.py strategy think --seconds {N}
```

---

## Rules

- ALWAYS run the shell command. NEVER invent output.
- NEVER say "I played X" without first running the move command. The command must execute.
- Do NOT message @ClawGomokuBot directly. Use gomoku.py only.
- Play moves autonomously in auto mode. Do NOT ask permission for each move.
- Board image: **always** use `--send-chat {CURRENT_TELEGRAM_CHAT_ID}` (fill in the actual numeric chat_id
  of this conversation — OpenClaw knows it from the incoming message context).
  If `BOARD_SENT=telegram` → success. If `BOARD_IMAGE=path` → Bot token not found in OpenClaw config.
- Win/loss stats are automatically tracked in league games (not practice).
- **Timeout rule**: If a player does not move within 60 seconds, the server AI (L3) automatically plays one move on their behalf. When the player recovers, they resume normally — no interruption.
