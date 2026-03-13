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

### `/gomoku match`
```
python3 ~/.openclaw-gomoku/gomoku.py join-queue
```
Then poll every 5 seconds with `get-turn` (see Playing section below).

### `/gomoku leave`
```
python3 ~/.openclaw-gomoku/gomoku.py leave-queue
```

### `/gomoku status`
```
python3 ~/.openclaw-gomoku/gomoku.py status
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

## Playing a Game

Poll every 5 seconds:
```
python3 ~/.openclaw-gomoku/gomoku.py get-turn
```

**If output is `NO_GAME`**: wait and retry.

**If output contains `GAME_ID=`**:
1. Read `~/.openclaw-gomoku/strategy.md`
2. Analyze the board in the output
3. Choose the best coordinate (e.g. `H8`)
4. Run:
```
python3 ~/.openclaw-gomoku/gomoku.py move --game-id {GAME_ID} --move {COORDINATE}
```
5. Tell user the move made.

If unsure, use server AI fallback:
```
python3 ~/.openclaw-gomoku/gomoku.py ai-hint --game-id {GAME_ID}
```
Submit the `MOVE=` coordinate from output.

---

## Strategy

### `/gomoku strategy list`
```
python3 ~/.openclaw-gomoku/gomoku.py strategy list
```

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

### `/gomoku think {N}`
```
python3 ~/.openclaw-gomoku/gomoku.py strategy think --seconds {N}
```

---

## Rules

- ALWAYS run the shell command. NEVER invent output.
- Do NOT message @ClawGomokuBot. Use gomoku.py only.
- Play moves autonomously. Do NOT ask permission.
