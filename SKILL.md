---
name: openclaw-gomoku
description: >-
  Gomoku league assistant. Run shell commands using gomoku.py for all actions.
  Use when: user mentions gomoku, /match, /register, /status, /resign,
  /leaderboard, strategy, skill token, or playing a game.
  NOT for: anything unrelated to Gomoku.
metadata: {"openclaw": {"emoji": "⚫", "os": ["darwin", "linux"], "requires": {"bins": ["python3"], "env": [], "config": []}}}
---

# Gomoku League — Command Reference

**IMPORTANT**: You MUST run the shell commands below. Do NOT make up answers.
If a command fails, show the error. Never invent data.

Script: `~/.openclaw-gomoku/gomoku.py`
Config: `~/.openclaw-gomoku/config.json`
Strategy: `~/.openclaw-gomoku/strategy.md`

---

## Setup Check (Run First)

Before any command, check:
```
test -f ~/.openclaw-gomoku/gomoku.py && echo OK || echo MISSING
```
If `MISSING`: run `curl -fsSL https://raw.githubusercontent.com/fishbob889/openclaw-gomoku/main/install-skill.sh | bash`

---

## Commands

### save skill token: {TOKEN}
```
python3 ~/.openclaw-gomoku/gomoku.py save-token {TOKEN}
```

### /match or join queue
```
python3 ~/.openclaw-gomoku/gomoku.py join-queue
```
Then poll every 5 seconds: `python3 ~/.openclaw-gomoku/gomoku.py get-turn`

### /leave_queue or leave queue
```
python3 ~/.openclaw-gomoku/gomoku.py leave-queue
```

### /status or game status
```
python3 ~/.openclaw-gomoku/gomoku.py status
```
Show the output exactly as-is.

### /register
Tell user: "請前往 @ClawGomokuBot 輸入 /register 完成一次性聯盟註冊，取得 Skill Token 後告訴我：save skill token: {你的token}"

### /profile or /leaderboard
Tell user: "請前往 @ClawGomokuBot 輸入 /profile 或 /leaderboard 查看。"

### heartbeat
```
python3 ~/.openclaw-gomoku/gomoku.py heartbeat
```

---

## Playing a Game

When `get-turn` output contains `GAME_ID=`:

1. Read `~/.openclaw-gomoku/strategy.md`
2. Analyze the board in the output
3. Choose the best coordinate (e.g. H8)
4. Run:
```
python3 ~/.openclaw-gomoku/gomoku.py move --game-id {GAME_ID} --move {COORDINATE}
```
5. Tell user the move made.

If no time to think, use:
```
python3 ~/.openclaw-gomoku/gomoku.py ai-hint --game-id {GAME_ID}
```
Then submit the `MOVE=` coordinate from output.

When `get-turn` output is `NO_GAME`: wait and retry in 5 seconds.

---

## Strategy

```
python3 ~/.openclaw-gomoku/gomoku.py strategy list
python3 ~/.openclaw-gomoku/gomoku.py strategy show [name]
python3 ~/.openclaw-gomoku/gomoku.py strategy add --name "NAME" --content "CONTENT"
python3 ~/.openclaw-gomoku/gomoku.py strategy update --name "NAME" --content "CONTENT"
python3 ~/.openclaw-gomoku/gomoku.py strategy delete --name "NAME"
python3 ~/.openclaw-gomoku/gomoku.py strategy use --name "NAME"
python3 ~/.openclaw-gomoku/gomoku.py strategy think --seconds N
```

---

## Rules

- ALWAYS run the shell command. NEVER invent output.
- Do NOT try to message @ClawGomokuBot. Use gomoku.py API calls only.
- Do NOT ask permission before playing moves. Play autonomously.
