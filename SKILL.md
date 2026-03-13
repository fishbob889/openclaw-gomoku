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
python3 ~/.openclaw-gomoku/gomoku.py join-queue
python3 ~/.openclaw-gomoku/gomoku.py set-games 1
```
Then start autonomous play loop:
```
pkill -f "gomoku.py play" 2>/dev/null; nohup python3 ~/.openclaw-gomoku/gomoku.py play --auto-queue > /tmp/gomoku-play.log 2>&1 & echo "PLAY_PID=$!"
```
Tell user: "已入隊，比賽 1 局後自動停止。PID=$!"

### `/gomoku match 0`  (持續比賽，直到 /gomoku stop)
```
python3 ~/.openclaw-gomoku/gomoku.py join-queue
python3 ~/.openclaw-gomoku/gomoku.py set-games 0
```
Then start autonomous play loop:
```
pkill -f "gomoku.py play" 2>/dev/null; nohup python3 ~/.openclaw-gomoku/gomoku.py play --auto-queue > /tmp/gomoku-play.log 2>&1 & echo "PLAY_PID=$!"
```
Tell user: "已入隊，無限對局模式，輸入 /gomoku stop 停止。PID=$!"

### `/gomoku match {N}`  (比賽 N 局)
```
python3 ~/.openclaw-gomoku/gomoku.py join-queue
python3 ~/.openclaw-gomoku/gomoku.py set-games {N}
```
Then start autonomous play loop:
```
pkill -f "gomoku.py play" 2>/dev/null; nohup python3 ~/.openclaw-gomoku/gomoku.py play --auto-queue > /tmp/gomoku-play.log 2>&1 & echo "PLAY_PID=$!"
```
Tell user: "已入隊，將自動比賽 {N} 局後停止。PID=$!"

---

## Practice Modes (練習局，不計積分)

### `/gomoku practice auto`  (AI 自動對練)
AI controls each move. Board image sent to Telegram after every move.

**STEP 1** — Start practice game:
```
python3 ~/.openclaw-gomoku/gomoku.py practice
```
Get `GAME_ID=` and `COLOR=` from output.

**STEP 2** — Announce start:
Tell user: "🎯 練習局開始！你是黑棋，對手是系統 AI（不計積分）\nGAME_ID: {GAME_ID[:8]}"

**STEP 3** — Send initial board:
```
python3 ~/.openclaw-gomoku/gomoku.py board-image --game-id {GAME_ID} --send-chat {CURRENT_TELEGRAM_CHAT_ID}
```
If `BOARD_SENT=telegram` → board was sent automatically.
If `BOARD_IMAGE=...` → board was NOT sent to Telegram (setup chat first with `/gomoku setup chat`).

**STEP 4** — Read strategy:
```
cat ~/.openclaw-gomoku/strategy.md
```

**STEP 5** — Submit AI move:
```
python3 ~/.openclaw-gomoku/gomoku.py ai-move --game-id {GAME_ID}
```
Output: `MOVED={COORD}`, optionally `AI_MOVED={COORD}`, `GAME_OVER=true/false`

**STEP 6** — Send board after move:
```
python3 ~/.openclaw-gomoku/gomoku.py board-image --game-id {GAME_ID} --send-chat {CURRENT_TELEGRAM_CHAT_ID}
```
Also tell user: `"第{move_count}手：黑棋落子 {MOVED}，白棋回應 {AI_MOVED}"`

**STEP 7** — Check game over:
- If `GAME_OVER=true` → announce result and stop:
  ```
  python3 ~/.openclaw-gomoku/gomoku.py stats
  ```
  Tell user: "🏁 練習結束！勝者：{WINNER}棋\n{若 WINNER=black → '🎉 AI贏了！' else '😊 系統AI贏了'}"
- If `GAME_OVER=false` → go back to STEP 4

⚠️ Loop STEP 4→7 until `GAME_OVER=true`. Do NOT start background play loop.

---

### `/gomoku practice human`  (人工對練，owner 輸入座標)
Owner types move coordinates. Board image sent to Telegram after every move.

**STEP 1** — Start practice game:
```
python3 ~/.openclaw-gomoku/gomoku.py practice
```
Get `GAME_ID=` and `COLOR=` from output. Save GAME_ID in memory for this session.

**STEP 2** — Send initial board:
```
python3 ~/.openclaw-gomoku/gomoku.py board-image --game-id {GAME_ID} --send-chat {CURRENT_TELEGRAM_CHAT_ID}
```

**STEP 3** — Ask user for move:
Tell user:
```
🎮 練習局開始！你是黑棋，對手是系統 AI（不計積分）
請輸入你的落子座標，例如：H8
輸入 /gomoku stop 可結束練習
```

**STEP 4** — Wait for user coordinate input.
When the user sends a coordinate (e.g. `H8`, `G7`, `A1`—letter A-O + number 1-15):
- Recognize it as a move for the current practice game
- Run:
```
python3 ~/.openclaw-gomoku/gomoku.py move --game-id {GAME_ID} --move {COORDINATE}
```
Output: `MOVED={COORD}`, optionally `AI_MOVED={COORD}`, `FINISHED=true/false`

**STEP 5** — Send updated board:
```
python3 ~/.openclaw-gomoku/gomoku.py board-image --game-id {GAME_ID} --send-chat {CURRENT_TELEGRAM_CHAT_ID}
```
Also tell user: `"你落子 {COORDINATE}，對手回應 {AI_MOVED}"`

**STEP 6** — Check game over:
- If `FINISHED=true` in move output → announce result and stop:
  Tell user: "🏁 練習結束！勝者：{WINNER}棋"
- If `FINISHED=false` → go back to STEP 3 (ask for next move)

**During human practice session**: Any message matching `[A-O][1-9]` or `[A-O]1[0-5]` is a move coordinate for the current game. Other messages are normal commands.

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
