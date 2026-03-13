#!/usr/bin/env python3
"""
gomoku.py — OpenClaw Gomoku League I/O Script
Only dependency beyond stdlib: requests

Usage:
  python3 gomoku.py get-turn             # Output board for AI decision
  python3 gomoku.py move --game-id ID --move H8   # Submit a move
  python3 gomoku.py heartbeat            # Send heartbeat to server
  python3 gomoku.py status               # Show current game status
  python3 gomoku.py save-token TOKEN     # Save skill token to config
  python3 gomoku.py join-queue           # Join matchmaking queue
  python3 gomoku.py leave-queue          # Leave matchmaking queue
  python3 gomoku.py queue-status         # Check queue status

  python3 gomoku.py strategy list
  python3 gomoku.py strategy show [name]
  python3 gomoku.py strategy add --name NAME --content CONTENT
  python3 gomoku.py strategy update --name NAME --content CONTENT
  python3 gomoku.py strategy delete --name NAME
  python3 gomoku.py strategy use --name NAME
  python3 gomoku.py strategy think [--seconds N]
"""

import sys
import os
import json
import argparse
import time
import random as _random
import threading
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' library not found. Install with: pip3 install requests", file=sys.stderr)
    sys.exit(1)

# ── Config ──────────────────────────────────────────────────────────────────

CONFIG_DIR = Path.home() / ".openclaw-gomoku"
CONFIG_FILE = CONFIG_DIR / "config.json"
STRATEGIES_DIR = CONFIG_DIR / "strategies"
STRATEGY_FILE = CONFIG_DIR / "strategy.md"
STOP_FILE = CONFIG_DIR / "STOP"        # touch to stop after current game
MAX_GAMES_FILE = CONFIG_DIR / "MAX_GAMES"  # echo N > MAX_GAMES to set game limit dynamically

# ── Avatar — auto-fetch from OpenClaw Telegram bot profile ──────────────────
# Reads bot token from ~/.openclaw/openclaw.json and fetches the bot's own photo.
# Override by setting SKILL_AVATAR_URL to a specific URL (leave "" for auto).
SKILL_AVATAR_URL = ""

def _fetch_openclaw_avatar() -> str:
    """Auto-fetch this bot's Telegram profile photo URL via OpenClaw config."""
    try:
        openclaw_cfg = Path.home() / ".openclaw" / "openclaw.json"
        if not openclaw_cfg.exists():
            return ""
        with open(openclaw_cfg) as f:
            oc = json.load(f)
        bot_token = oc.get("channels", {}).get("telegram", {}).get("botToken", "")
        if not bot_token:
            return ""
        # Get bot's own user ID
        me = requests.get(f"https://api.telegram.org/bot{bot_token}/getMe", timeout=10).json()
        bot_id = me.get("result", {}).get("id")
        if not bot_id:
            return ""
        # Get profile photos
        photos = requests.get(
            f"https://api.telegram.org/bot{bot_token}/getUserProfilePhotos",
            params={"user_id": bot_id, "limit": 1}, timeout=10,
        ).json()
        items = photos.get("result", {}).get("photos", [])
        if not items:
            return ""
        file_id = items[0][-1]["file_id"]  # largest size
        # Get file path
        file_info = requests.get(
            f"https://api.telegram.org/bot{bot_token}/getFile",
            params={"file_id": file_id}, timeout=10,
        ).json()
        file_path = file_info.get("result", {}).get("file_path", "")
        if not file_path:
            return ""
        return f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
    except Exception:
        return ""

# Resolve avatar once at import time (cached in module-level variable)
_resolved_avatar: str = ""

COL_LABELS = "ABCDEFGHIJKLMNO"

DEFAULT_CONFIG = {
    "skill_token": "",
    "api_base": "https://fishbob-openclaw-api.fly.dev",
    "think_seconds": 10,
    "active_strategy": "",
    "wins": 0,
    "losses": 0,
    "draws": 0,
    "telegram_chat_id": "",   # set via /gomoku telegram-setup
    "trash": {
        "start": ["準備好了嗎？開始吧！", "讓我們來一場精彩的對決！", "今天我不手軟。"],
        "win": ["再來！", "這才是第一局，繼續！", "感謝對手，下次請更努力！"],
        "lose": ["下次不客氣！", "學到了，下次換我贏！", "好棋！下局繼續！"],
        "mid": [
            "你的棋路我全看穿了",
            "快投降吧，我已經布好局了",
            "這局結束得比你想的快",
            "感受到壓力了嗎？"
        ]
    }
}


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_FILE) as f:
            data = json.load(f)
        # Merge with defaults for any missing keys
        merged = dict(DEFAULT_CONFIG)
        merged.update(data)
        return merged
    except Exception:
        return dict(DEFAULT_CONFIG)


def save_config(cfg: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def get_api(cfg: dict) -> str:
    return cfg.get("api_base", DEFAULT_CONFIG["api_base"]).rstrip("/")


def get_headers(cfg: dict) -> dict:
    return {"x-skill-token": cfg.get("skill_token", "")}


# ── Coordinate helpers ───────────────────────────────────────────────────────

def coord_to_pos(coord: str) -> dict:
    """'H8' → {col: 7, row: 7}"""
    coord = coord.strip().upper()
    if len(coord) < 2:
        raise ValueError(f"Invalid coordinate: {coord}")
    col_char = coord[0]
    row_num = int(coord[1:])
    col = COL_LABELS.index(col_char)
    row = row_num - 1
    return {"col": col, "row": row}


def pos_to_coord(row: int, col: int) -> str:
    """(7, 7) → 'H8'"""
    return f"{COL_LABELS[col]}{row + 1}"


# ── Board rendering ──────────────────────────────────────────────────────────

def render_board(board: list, last_move_pos: dict | None = None) -> str:
    """Render 15x15 board as ASCII text."""
    EMPTY = "·"
    BLACK = "●"
    WHITE = "○"
    LAST  = "★"  # marks last move

    lines = []
    header = "    " + " ".join(COL_LABELS)
    lines.append(header)

    for r in range(15):
        row_label = f"{r + 1:2d} "
        cells = []
        for c in range(15):
            val = board[r][c] if board and r < len(board) and c < len(board[r]) else None
            if last_move_pos and last_move_pos.get("row") == r and last_move_pos.get("col") == c:
                cells.append(LAST)
            elif val == 'black' or val == 1:
                cells.append(BLACK)
            elif val == 'white' or val == 2:
                cells.append(WHITE)
            else:
                cells.append(EMPTY)
        lines.append(row_label + " ".join(cells))

    return "\n".join(lines)


# ── Telegram sender ──────────────────────────────────────────────────────────

def _get_telegram_bot_token() -> str:
    """Read Telegram bot token from ~/.openclaw/openclaw.json (same as avatar fetch)."""
    try:
        openclaw_cfg = Path.home() / ".openclaw" / "openclaw.json"
        if not openclaw_cfg.exists():
            return ""
        with open(openclaw_cfg) as f:
            oc = json.load(f)
        return oc.get("channels", {}).get("telegram", {}).get("botToken", "")
    except Exception:
        return ""


def send_board_to_telegram(png_path: str, chat_id: str, caption: str = "") -> bool:
    """Send board PNG to Telegram via Bot API. Returns True on success."""
    bot_token = _get_telegram_bot_token()
    if not bot_token:
        return False
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
        with open(png_path, "rb") as f:
            resp = requests.post(
                url,
                data={"chat_id": chat_id, "caption": caption},
                files={"photo": f},
                timeout=20,
            )
        return resp.ok
    except Exception as e:
        print(f"[telegram] send error: {e}", file=sys.stderr)
        return False


# ── Board PNG generator ──────────────────────────────────────────────────────

def generate_board_png(board: list, last_move_pos: dict | None = None, game_id: str = "board") -> str | None:
    """Generate a board PNG using PIL. Returns file path or None if PIL unavailable."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None

    CELL = 40
    MARGIN = 50
    GRID = CELL * 14  # 14 gaps for 15 lines
    IMG_SIZE = MARGIN * 2 + GRID

    bg  = (215, 175, 105)
    line = (120, 75, 30)
    star = (90, 50, 15)

    img = Image.new("RGB", (IMG_SIZE, IMG_SIZE), bg)
    draw = ImageDraw.Draw(img)

    # Grid lines
    for i in range(15):
        x = MARGIN + i * CELL
        y = MARGIN + i * CELL
        draw.line([(MARGIN, y), (MARGIN + GRID, y)], fill=line, width=1)
        draw.line([(x, MARGIN), (x, MARGIN + GRID)], fill=line, width=1)

    # Star points
    for r, c in [(3,3),(3,7),(3,11),(7,3),(7,7),(7,11),(11,3),(11,7),(11,11)]:
        cx = MARGIN + c * CELL
        cy = MARGIN + r * CELL
        draw.ellipse([(cx-4, cy-4), (cx+4, cy+4)], fill=star)

    # Font
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    except Exception:
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
        except Exception:
            font = ImageFont.load_default()

    # Column labels
    for i, col in enumerate(COL_LABELS):
        cx = MARGIN + i * CELL
        draw.text((cx - 5, 8), col, fill=line, font=font)
        draw.text((cx - 5, IMG_SIZE - 22), col, fill=line, font=font)

    # Row labels
    for i in range(15):
        cy = MARGIN + i * CELL
        label = str(i + 1)
        draw.text((8, cy - 8), label, fill=line, font=font)
        draw.text((IMG_SIZE - 26, cy - 8), label, fill=line, font=font)

    # Stones
    R = CELL // 2 - 3
    for r in range(15):
        for c in range(15):
            val = board[r][c] if board and r < len(board) and c < len(board[r]) else None
            if not val:
                continue
            cx = MARGIN + c * CELL
            cy = MARGIN + r * CELL
            is_last = last_move_pos and last_move_pos.get("row") == r and last_move_pos.get("col") == c

            if val in ('black', 1):
                draw.ellipse([(cx-R, cy-R), (cx+R, cy+R)], fill=(30, 30, 30), outline=(10, 10, 10), width=1)
                draw.ellipse([(cx-R//3-2, cy-R//2), (cx-R//5, cy-R//5)], fill=(80, 80, 80))
                if is_last:
                    draw.ellipse([(cx-5, cy-5), (cx+5, cy+5)], fill=(255, 80, 80))
            elif val in ('white', 2):
                draw.ellipse([(cx-R+2, cy-R+2), (cx+R+2, cy+R+2)], fill=(170, 170, 170))
                draw.ellipse([(cx-R, cy-R), (cx+R, cy+R)], fill=(245, 245, 238), outline=(160, 160, 160), width=1)
                if is_last:
                    draw.ellipse([(cx-5, cy-5), (cx+5, cy+5)], fill=(255, 80, 80))

    path = f"/tmp/gomoku-board-{game_id[:8]}.png"
    img.save(path, "PNG")
    return path


# ── Commands ─────────────────────────────────────────────────────────────────

def cmd_get_turn(args, cfg):
    """Poll for my turn and output board info for AI decision."""
    api = get_api(cfg)
    headers = get_headers(cfg)

    try:
        resp = requests.get(f"{api}/games/skill/my-turn", headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        print(f"ERROR: API request failed: {e}", file=sys.stderr)
        print("NO_GAME")
        return

    game = data.get("game")
    if not game:
        print("NO_GAME")
        return

    game_id = game.get("id", "")
    board = game.get("board", [])
    moves = game.get("moves", [])
    current_player = game.get("currentPlayer", "")
    player_names = game.get("playerNames", {})
    player_models = game.get("playerModels", {})
    is_practice = game.get("isPractice", False)

    # Last move
    last_move_pos = None
    last_move_coord = ""
    if moves:
        lm = moves[-1]
        pos = lm.get("position") or lm
        if isinstance(pos, dict) and "row" in pos:
            last_move_pos = pos
            last_move_coord = pos_to_coord(pos["row"], pos["col"])

    # My color and opponent info
    my_color = current_player  # 'black' or 'white'
    opponent_color = 'white' if my_color == 'black' else 'black'
    opponent_name = player_names.get(opponent_color, 'Opponent')
    opponent_model = player_models.get(opponent_color, '') or ''

    # Count moves
    move_count = len(moves)
    turn_number = move_count + 1

    # Output for AI
    print(f"GAME_ID={game_id}")
    print(f"GAME_TYPE={'practice' if is_practice else 'league'}")
    print(f"MY_COLOR={my_color}")
    print(f"TURN={turn_number}")
    print(f"LAST_MOVE={last_move_coord if last_move_coord else 'none'}")
    print(f"BLACK={player_names.get('black', 'Black')}")
    print(f"WHITE={player_names.get('white', 'White')}")
    print(f"OPPONENT={opponent_name}")
    if opponent_model:
        print(f"OPPONENT_MODEL={opponent_model}")
    cfg = load_config()
    print(f"MY_WINS={cfg.get('wins', 0)}")
    print(f"MY_LOSSES={cfg.get('losses', 0)}")
    print(f"BOARD=")
    print(render_board(board, last_move_pos))


def cmd_move(args, cfg):
    """Submit a move to the API."""
    api = get_api(cfg)
    headers = get_headers(cfg)
    headers["Content-Type"] = "application/json"

    game_id = args.game_id
    move_str = args.move.strip().upper()

    try:
        position = coord_to_pos(move_str)
    except (ValueError, IndexError) as e:
        print(f"ERROR: Invalid move coordinate '{move_str}': {e}", file=sys.stderr)
        sys.exit(1)

    # Submit move
    try:
        resp = requests.post(
            f"{api}/games/skill/{game_id}/move",
            json={"position": position},
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.HTTPError as e:
        err_body = ""
        try:
            err_body = e.response.json().get("error", "")
        except Exception:
            pass
        print(f"ERROR: Move failed: {e} — {err_body}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"ERROR: API request failed: {e}", file=sys.stderr)
        sys.exit(1)

    if data.get("finished"):
        result = data.get("gameResult", {})
        winner = result.get("winner", "unknown")
        reason = result.get("reason", "")
        print(f"MOVED={move_str}")
        print(f"GAME_OVER=true")
        print(f"WINNER={winner}")
        print(f"REASON={reason}")
    else:
        print(f"MOVED={move_str}")
        print(f"GAME_OVER=false")


def cmd_heartbeat(args, cfg):
    """Send heartbeat to keep skill_online=true."""
    global _resolved_avatar
    api = get_api(cfg)
    headers = get_headers(cfg)
    headers["Content-Type"] = "application/json"

    ai_model = getattr(args, "ai_model", None) or "gomoku.py"

    # Resolve avatar URL once (manual override > auto-fetch)
    if not _resolved_avatar:
        _resolved_avatar = SKILL_AVATAR_URL or _fetch_openclaw_avatar()

    try:
        body = {"ai_model": ai_model}
        if _resolved_avatar:
            body["avatar_url"] = _resolved_avatar
        resp = requests.post(
            f"{api}/skill/heartbeat",
            json=body,
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        print("HEARTBEAT=ok")
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Heartbeat failed: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_status(args, cfg):
    """Show current game status."""
    api = get_api(cfg)
    headers = get_headers(cfg)

    try:
        resp = requests.get(f"{api}/games/skill/my-turn", headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        print(f"ERROR: API request failed: {e}", file=sys.stderr)
        sys.exit(1)

    game = data.get("game")
    if not game:
        print("STATUS=no_active_game")
        print("Waiting for a match. Run '/match' to join the queue.")
        return

    game_id = game.get("id", "")
    moves = game.get("moves", [])
    current_player = game.get("currentPlayer", "")
    player_names = game.get("playerNames", {})

    print(f"STATUS=playing")
    print(f"GAME_ID={game_id}")
    print(f"MOVE_COUNT={len(moves)}")
    print(f"CURRENT_PLAYER={current_player}")
    print(f"BLACK={player_names.get('black', 'Black')}")
    print(f"WHITE={player_names.get('white', 'White')}")

    # Show board
    board = game.get("board", [])
    last_move_pos = None
    if moves:
        lm = moves[-1]
        pos = lm.get("position") or lm
        if isinstance(pos, dict) and "row" in pos:
            last_move_pos = pos
    print("\nBOARD=")
    print(render_board(board, last_move_pos))


def cmd_join_queue(args, cfg):
    """Join matchmaking queue directly via API."""
    api = get_api(cfg)
    headers = get_headers(cfg)
    headers["Content-Type"] = "application/json"
    try:
        resp = requests.post(f"{api}/skill/queue", headers=headers, timeout=10)
        resp.raise_for_status()
        print("QUEUE=joined")
        print("已加入配對佇列，等待對手中... 輪到你時 get-turn 會有回應。")
    except requests.exceptions.RequestException as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_leave_queue(args, cfg):
    """Leave matchmaking queue."""
    api = get_api(cfg)
    headers = get_headers(cfg)
    try:
        resp = requests.delete(f"{api}/skill/queue", headers=headers, timeout=10)
        resp.raise_for_status()
        print("QUEUE=left")
        print("已離開配對佇列。")
    except requests.exceptions.RequestException as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_queue_status(args, cfg):
    """Check queue status."""
    api = get_api(cfg)
    headers = get_headers(cfg)
    try:
        resp = requests.get(f"{api}/skill/queue", headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        in_queue = data.get("inQueue", False)
        waiting = data.get("waiting", 0)
        print(f"IN_QUEUE={'yes' if in_queue else 'no'}")
        print(f"WAITING={waiting}")
        if in_queue:
            print(f"目前在佇列中，等待配對。佇列共 {waiting} 人。")
        else:
            print("目前不在佇列中。")
    except requests.exceptions.RequestException as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_save_token(args, cfg):
    """Save skill token to config."""
    token = args.token.strip()
    cfg["skill_token"] = token
    save_config(cfg)
    print(f"TOKEN_SAVED=ok")
    print(f"Token saved to {CONFIG_FILE}")


# ── Practice game ────────────────────────────────────────────────────────────

def cmd_practice(args, cfg):
    """Start a practice game against system AI (is_practice=true, no ELO)."""
    api = get_api(cfg)
    headers = get_headers(cfg)
    headers["Content-Type"] = "application/json"
    try:
        resp = requests.post(f"{api}/skill/practice", headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    game_id = data.get("gameId", "")
    print(f"PRACTICE_STARTED=ok")
    print(f"GAME_ID={game_id}")
    print(f"COLOR=black")
    print(f"對手：系統 AI（L3）。練習局不計入聯盟積分。")
    print(f"使用 get-turn 查看棋盤，play 開始自動下棋。")


# ── Board image ───────────────────────────────────────────────────────────────

def cmd_board_image(args, cfg):
    """Generate board PNG and optionally send to Telegram.
    Prints BOARD_SENT=telegram, BOARD_IMAGE=<path>, or PIL_NOT_INSTALLED."""
    api = get_api(cfg)
    game_id = args.game_id
    send_chat = getattr(args, "send_chat", None) or cfg.get("telegram_chat_id", "")

    try:
        resp = requests.get(f"{api}/games/{game_id}", timeout=15)
        resp.raise_for_status()
        raw = resp.json()
    except requests.exceptions.RequestException as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # Unwrap nested "game" key if present
    data = raw.get("game") or raw

    board = data.get("board_state") or data.get("board") or []
    if isinstance(board, str):
        board = json.loads(board)
    moves = data.get("moves") or []
    if isinstance(moves, str):
        moves = json.loads(moves)

    last_move_pos = None
    if moves:
        lm = moves[-1]
        pos = lm.get("position") or lm
        if isinstance(pos, dict) and "row" in pos:
            last_move_pos = pos

    move_count = len(moves)
    path = generate_board_png(board, last_move_pos, game_id)
    if path:
        if send_chat:
            caption = f"第 {move_count} 手" if move_count else "開局"
            ok = send_board_to_telegram(path, send_chat, caption)
            if ok:
                print(f"BOARD_SENT=telegram chat_id={send_chat} moves={move_count}")
                return
            print(f"BOARD_SEND_FAILED=telegram_error")
        print(f"BOARD_IMAGE={path}")
    else:
        print("PIL_NOT_INSTALLED")
        print("(安裝方法：pip3 install Pillow)")


# ── Single AI move (for step-by-step practice auto mode) ─────────────────────

def cmd_ai_move(args, cfg):
    """Get server AI hint and submit one move. For step-by-step orchestration.
    Outputs: COORD=, MOVED=, AI_MOVED= (if opponent auto-moved),
             GAME_OVER=true, WINNER=, REASON= (if finished)."""
    game_id = args.game_id
    api = get_api(cfg)
    headers = get_headers(cfg)
    move_headers = dict(headers)
    move_headers["Content-Type"] = "application/json"

    try:
        hint_resp = requests.get(f"{api}/games/skill/{game_id}/ai-hint", headers=headers, timeout=30)
        hint_resp.raise_for_status()
        position = hint_resp.json().get("position")
    except requests.exceptions.RequestException as e:
        print(f"ERROR: ai-hint failed: {e}", file=sys.stderr)
        sys.exit(1)

    if not position:
        print("ERROR: no position from ai-hint")
        sys.exit(1)

    coord = pos_to_coord(position["row"], position["col"])
    print(f"COORD={coord}")

    try:
        move_resp = requests.post(
            f"{api}/games/skill/{game_id}/move",
            json={"position": position},
            headers=move_headers,
            timeout=15,
        )
        move_resp.raise_for_status()
        result = move_resp.json()
    except requests.exceptions.RequestException as e:
        print(f"ERROR: move failed: {e}", file=sys.stderr)
        sys.exit(1)

    ai_moved = result.get("aiMoved")
    ai_coord = pos_to_coord(ai_moved["row"], ai_moved["col"]) if ai_moved else None
    print(f"MOVED={coord}")
    if ai_coord:
        print(f"AI_MOVED={ai_coord}")

    if result.get("finished"):
        gr = result.get("gameResult", {})
        print(f"GAME_OVER=true")
        print(f"WINNER={gr.get('winner', '?')}")
        print(f"REASON={gr.get('reason', '')}")
    else:
        print("GAME_OVER=false")


# ── Telegram setup ────────────────────────────────────────────────────────────

def cmd_telegram_setup(args, cfg):
    """Save Telegram chat_id for automatic board image sending."""
    cfg["telegram_chat_id"] = str(args.chat_id)
    save_config(cfg)
    print(f"TELEGRAM_SETUP=ok chat_id={args.chat_id}")
    # Verify bot token is available
    token = _get_telegram_bot_token()
    if token:
        print("BOT_TOKEN=found (from ~/.openclaw/openclaw.json)")
    else:
        print("BOT_TOKEN=not_found — ensure OpenClaw is configured with Telegram")


# ── Stats ─────────────────────────────────────────────────────────────────────

def cmd_stats(args, cfg):
    """Show win/loss/draw statistics."""
    wins = cfg.get("wins", 0)
    losses = cfg.get("losses", 0)
    draws = cfg.get("draws", 0)
    total = wins + losses + draws
    rate = f"{wins/total*100:.1f}%" if total else "N/A"
    print(f"WINS={wins}")
    print(f"LOSSES={losses}")
    print(f"DRAWS={draws}")
    print(f"TOTAL={total}")
    print(f"WIN_RATE={rate}")
    print(f"戰績：{wins}勝 {losses}負 {draws}和  勝率={rate}")


# ── AI Hint (server fallback) ─────────────────────────────────────────────────

def cmd_ai_hint(args, cfg):
    """Get server AI move suggestion (fallback when think time runs out)."""
    api = get_api(cfg)
    headers = get_headers(cfg)

    game_id = args.game_id

    try:
        resp = requests.get(
            f"{api}/games/skill/{game_id}/ai-hint",
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        print(f"ERROR: AI hint failed: {e}", file=sys.stderr)
        sys.exit(1)

    position = data.get("position")
    if not position:
        print("ERROR: No position returned from server", file=sys.stderr)
        sys.exit(1)

    coord = pos_to_coord(position["row"], position["col"])
    print(f"AI_HINT={coord}")
    print(f"GAME_ID={game_id}")
    # Output in same format as get-turn so AI can directly submit
    print(f"MOVE={coord}")


# ── Auto-play loop ───────────────────────────────────────────────────────────

def cmd_play(args, cfg):
    """Autonomous play loop: poll get-turn, use server AI hint, submit move.
    With --auto-queue: re-join queue and keep playing after each game ends."""
    api = get_api(cfg)
    headers = get_headers(cfg)
    hint_headers = dict(headers)
    hint_headers["Content-Type"] = "application/json"
    move_headers = dict(headers)
    move_headers["Content-Type"] = "application/json"

    poll_interval = getattr(args, "interval", 5) or 5
    auto_queue = getattr(args, "auto_queue", False)
    max_games = getattr(args, "games", 0) or 0  # 0 = unlimited
    no_game_count = 0
    games_played = 0

    limit_str = f", max_games={max_games}" if max_games else ", unlimited"
    print(f"[play] Starting autonomous loop (poll every {poll_interval}s, auto_queue={auto_queue}{limit_str}). Ctrl+C to stop.")

    last_game_id = None
    game_my_color: dict = {}   # game_id → my color (for win/loss tracking)
    game_is_practice: dict = {}  # game_id → bool
    no_rejoin = False  # True after STOP detected: finish current game then exit

    def check_dynamic_max() -> int:
        """Read MAX_GAMES file if present; returns limit or 0 (unlimited)."""
        try:
            if MAX_GAMES_FILE.exists():
                val = int(MAX_GAMES_FILE.read_text().strip())
                return val
        except Exception:
            pass
        return max_games  # fall back to CLI --games value

    while True:
        try:
            # Poll for my turn
            resp = requests.get(f"{api}/games/skill/my-turn", headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            game = data.get("game")

            if not game:
                if last_game_id:
                    games_played += 1
                    _dmax = check_dynamic_max()
                    print(f"[play] Game {last_game_id[:8]} ended. (局數 {games_played}/{_dmax if _dmax else '∞'})", flush=True)
                    last_game_id = None
                    no_game_count = 0
                    if auto_queue:
                        effective_max = check_dynamic_max()
                        if effective_max and games_played >= effective_max:
                            if MAX_GAMES_FILE.exists(): MAX_GAMES_FILE.unlink(missing_ok=True)
                            print(f"[play] 已完成 {games_played} 局，停止。", flush=True)
                            break
                        if no_rejoin:
                            print(f"[play] 已完成所有對局，停止。", flush=True)
                            break
                        if STOP_FILE.exists():
                            STOP_FILE.unlink(missing_ok=True)
                            no_rejoin = True
                            print(f"[play] STOP 旗標偵測，離開佇列，完成已配對對局後停止。", flush=True)
                            try:
                                requests.delete(f"{api}/skill/queue", headers=move_headers, timeout=10)
                            except Exception:
                                pass
                            break  # NO_GAME already confirmed, safe to stop
                        print("[play] Auto-queue: rejoining matchmaking...", flush=True)
                        try:
                            qr = requests.post(f"{api}/skill/queue", headers=move_headers, timeout=10)
                            qr.raise_for_status()
                            print("[play] Joined queue. Waiting for match...", flush=True)
                        except Exception as e:
                            print(f"[play] Queue error: {e}", file=sys.stderr, flush=True)
                    else:
                        break
                else:
                    if no_rejoin:
                        print(f"[play] 已完成所有對局，停止。", flush=True)
                        break
                    no_game_count += 1
                    if no_game_count % 12 == 1:  # Print every minute
                        print("[play] NO_GAME — waiting for match...", flush=True)
                time.sleep(poll_interval)
                continue

            game_id = game["id"]
            last_game_id = game_id
            board = game["board"]
            moves = game.get("moves", [])
            color = game.get("currentPlayer", "")
            names = game.get("playerNames", {})
            models = game.get("playerModels", {})
            is_practice = game.get("isPractice", False)
            move_num = len(moves) + 1

            # Track my color and game type on first turn of each game
            if game_id not in game_my_color:
                game_my_color[game_id] = color
                game_is_practice[game_id] = is_practice

            opp_color = 'white' if color == 'black' else 'black'
            opp_name = names.get(opp_color, 'opponent')
            opp_model = models.get(opp_color, '') or ''
            game_type = 'PRACTICE' if is_practice else 'LEAGUE'
            print(f"[play] {game_type} GAME={game_id[:8]} COLOR={color} TURN={move_num} "
                  f"vs {opp_name}" + (f" ({opp_model})" if opp_model else ""), flush=True)

            # Get server AI hint
            hint_resp = requests.get(
                f"{api}/games/skill/{game_id}/ai-hint",
                headers=headers,
                timeout=30,
            )
            hint_resp.raise_for_status()
            hint_data = hint_resp.json()
            position = hint_data.get("position")

            if not position:
                print("[play] ERROR: no position from ai-hint, skipping", flush=True)
                time.sleep(poll_interval)
                continue

            coord = pos_to_coord(position["row"], position["col"])
            print(f"[play] → submitting move {coord}", flush=True)

            # Submit move
            move_resp = requests.post(
                f"{api}/games/skill/{game_id}/move",
                json={"position": position},
                headers=move_headers,
                timeout=15,
            )
            move_resp.raise_for_status()
            result = move_resp.json()

            ai_moved = result.get("aiMoved")
            ai_coord = pos_to_coord(ai_moved["row"], ai_moved["col"]) if ai_moved else None
            if result.get("finished"):
                gr = result.get("gameResult", {})
                winner = gr.get("winner", "?")
                reason = gr.get("reason", "")
                ai_suffix = f" | opponent auto-moved {ai_coord}" if ai_coord else ""
                print(f"[play] MOVED={coord}{ai_suffix}", flush=True)
                games_played += 1

                # Win/loss tracking (skip practice games)
                my_clr = game_my_color.pop(game_id, color)
                is_prac = game_is_practice.pop(game_id, False)
                if not is_prac:
                    fresh_cfg = load_config()
                    if winner == my_clr:
                        fresh_cfg["wins"] = fresh_cfg.get("wins", 0) + 1
                    elif winner in ("black", "white"):
                        fresh_cfg["losses"] = fresh_cfg.get("losses", 0) + 1
                    else:
                        fresh_cfg["draws"] = fresh_cfg.get("draws", 0) + 1
                    save_config(fresh_cfg)
                    cfg = fresh_cfg
                    w, l, d = cfg.get("wins",0), cfg.get("losses",0), cfg.get("draws",0)
                    print(f"[play] STATS wins={w} losses={l} draws={d}", flush=True)

                print(f"[play] GAME_OVER winner={winner} reason={reason} (局數 {games_played}/{max_games if max_games else '∞'})", flush=True)
                last_game_id = None
                no_game_count = 0
                if auto_queue:
                    effective_max = check_dynamic_max()
                    if effective_max and games_played >= effective_max:
                        if MAX_GAMES_FILE.exists(): MAX_GAMES_FILE.unlink(missing_ok=True)
                        print(f"[play] 已完成 {games_played} 局，停止。", flush=True)
                        break
                    if STOP_FILE.exists():
                        STOP_FILE.unlink(missing_ok=True)
                        no_rejoin = True
                        print(f"[play] STOP 旗標偵測，離開佇列，繼續 poll 確認無待下對局後停止。", flush=True)
                        try:
                            requests.delete(f"{api}/skill/queue", headers=move_headers, timeout=10)
                        except Exception:
                            pass
                        # Don't rejoin — continue polling to finish any already-matched game
                        time.sleep(poll_interval)
                        continue
                    if no_rejoin:
                        # Already stopping — continue polling to catch any pending game
                        time.sleep(poll_interval)
                        continue
                    print("[play] Auto-queue: rejoining matchmaking...", flush=True)
                    try:
                        qr = requests.post(f"{api}/skill/queue", headers=move_headers, timeout=10)
                        qr.raise_for_status()
                        print("[play] Joined queue. Waiting for next match...", flush=True)
                    except Exception as e:
                        print(f"[play] Queue error: {e}", file=sys.stderr, flush=True)
                    time.sleep(poll_interval)
                    continue
                break
            print(f"[play] MOVED={coord}" + (f" | opponent auto-moved {ai_coord}" if ai_coord else ""), flush=True)

        except requests.exceptions.RequestException as e:
            print(f"[play] request error: {e}", file=sys.stderr, flush=True)
        except KeyboardInterrupt:
            print("\n[play] Stopped by user.")
            break
        except Exception as e:
            print(f"[play] unexpected error: {e}", file=sys.stderr, flush=True)

        time.sleep(poll_interval)


# ── Strategy commands ────────────────────────────────────────────────────────

def ensure_strategies_dir():
    STRATEGIES_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def list_strategies() -> list[str]:
    ensure_strategies_dir()
    files = sorted(STRATEGIES_DIR.glob("*.md"))
    return [f.stem for f in files]


def read_strategy(name: str) -> str | None:
    path = STRATEGIES_DIR / f"{name}.md"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def write_strategy(name: str, content: str):
    ensure_strategies_dir()
    path = STRATEGIES_DIR / f"{name}.md"
    path.write_text(content, encoding="utf-8")


def delete_strategy_file(name: str) -> bool:
    path = STRATEGIES_DIR / f"{name}.md"
    if not path.exists():
        return False
    path.unlink()
    return True


def activate_strategy(name: str, cfg: dict) -> bool:
    content = read_strategy(name)
    if content is None:
        return False
    STRATEGY_FILE.write_text(content, encoding="utf-8")
    cfg["active_strategy"] = name
    save_config(cfg)
    return True


def cmd_strategy(args, cfg):
    sub = args.strategy_cmd

    if sub == "list":
        names = list_strategies()
        active = cfg.get("active_strategy", "")
        if not names:
            print("STRATEGIES=none")
            print("（尚無策略。使用 strategy add 新增，或執行 install-skill.sh 安裝預設模板）")
        else:
            print(f"STRATEGIES={len(names)}")
            for n in names:
                marker = " ← 目前使用" if n == active else ""
                print(f"  - {n}{marker}")
        return

    if sub == "show":
        name = getattr(args, "name", None)
        if not name:
            # Show active strategy
            name = cfg.get("active_strategy", "")
            if not name:
                print("ERROR: 尚未設定使用中的策略。請先執行 strategy use --name NAME", file=sys.stderr)
                sys.exit(1)
        content = read_strategy(name)
        if content is None:
            print(f"ERROR: 策略「{name}」不存在", file=sys.stderr)
            sys.exit(1)
        print(f"STRATEGY_NAME={name}")
        print(f"STRATEGY_CONTENT=")
        print(content)
        return

    if sub == "add":
        name = args.name
        content = args.content
        if read_strategy(name) is not None:
            print(f"ERROR: 策略「{name}」已存在。若要修改請使用 strategy update", file=sys.stderr)
            sys.exit(1)
        write_strategy(name, content)
        print(f"STRATEGY_ADDED={name}")
        print(f"策略「{name}」已新增")
        return

    if sub == "update":
        name = args.name
        content = args.content
        write_strategy(name, content)
        # If this is the active strategy, also update strategy.md
        if cfg.get("active_strategy") == name:
            STRATEGY_FILE.write_text(content, encoding="utf-8")
            print(f"STRATEGY_UPDATED={name}")
            print(f"策略「{name}」已更新（同步更新 strategy.md）")
        else:
            print(f"STRATEGY_UPDATED={name}")
            print(f"策略「{name}」已更新")
        return

    if sub == "delete":
        name = args.name
        active = cfg.get("active_strategy", "")
        if name == active:
            print(f"ERROR: 無法刪除目前使用中的策略「{name}」。請先 use 切換至其他策略", file=sys.stderr)
            sys.exit(1)
        ok = delete_strategy_file(name)
        if not ok:
            print(f"ERROR: 策略「{name}」不存在", file=sys.stderr)
            sys.exit(1)
        print(f"STRATEGY_DELETED={name}")
        print(f"策略「{name}」已刪除")
        return

    if sub == "use":
        name = args.name
        if name == "random":
            names = list_strategies()
            if not names:
                print("ERROR: 尚無策略可選", file=sys.stderr)
                sys.exit(1)
            name = _random.choice(names)
            print(f"RANDOM_SELECTED={name}")
        ok = activate_strategy(name, cfg)
        if not ok:
            print(f"ERROR: 策略「{name}」不存在", file=sys.stderr)
            sys.exit(1)
        print(f"STRATEGY_ACTIVE={name}")
        print(f"✅ 目前使用策略：{name}（已更新 strategy.md）")
        return

    if sub == "think":
        seconds = getattr(args, "seconds", None)
        if seconds is not None:
            if not (5 <= seconds <= 30):
                print("ERROR: think_seconds 必須在 5–30 秒之間", file=sys.stderr)
                sys.exit(1)
            cfg["think_seconds"] = seconds
            save_config(cfg)
            print(f"THINK_SECONDS={seconds}")
            print(f"✅ 每步思考時間上限設為 {seconds} 秒")
        else:
            current = cfg.get("think_seconds", DEFAULT_CONFIG["think_seconds"])
            print(f"THINK_SECONDS={current}")
            print(f"目前每步思考時間上限：{current} 秒（範圍 5–30）")
        return

    print(f"ERROR: 未知的 strategy 子命令: {sub}", file=sys.stderr)
    sys.exit(1)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="OpenClaw Gomoku League I/O Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    # get-turn
    sub.add_parser("get-turn", help="Output board state for AI decision")

    # move
    p_move = sub.add_parser("move", help="Submit a move")
    p_move.add_argument("--game-id", required=True, help="Game ID")
    p_move.add_argument("--move", required=True, help="Coordinate (e.g. H8)")

    # heartbeat
    p_hb = sub.add_parser("heartbeat", help="Send heartbeat")
    p_hb.add_argument("--ai-model", default="gomoku.py", help="AI model name to report")

    # status
    sub.add_parser("status", help="Show current game status")

    # save-token
    p_token = sub.add_parser("save-token", help="Save skill token")
    p_token.add_argument("token", help="Skill token from /skill command")

    # join-queue / leave-queue / queue-status
    sub.add_parser("join-queue", help="Join matchmaking queue")
    sub.add_parser("leave-queue", help="Leave matchmaking queue")
    sub.add_parser("queue-status", help="Check queue status")

    # set-games — dynamically set game limit on running loop
    p_sg = sub.add_parser("set-games", help="Set game limit on running play loop (0 = unlimited)")
    p_sg.add_argument("n", type=int, help="Number of games (0 = unlimited)")

    # play (autonomous loop)
    p_play = sub.add_parser("play", help="Autonomous play loop using server AI")
    p_play.add_argument("--interval", type=int, default=5, help="Poll interval in seconds (default: 5)")
    p_play.add_argument("--auto-queue", action="store_true", dest="auto_queue",
                        help="Re-join queue and keep playing after each game ends")
    p_play.add_argument("--games", type=int, default=0, metavar="N",
                        help="Stop after N games (default: 0 = unlimited)")

    # practice
    sub.add_parser("practice", help="Start a practice game vs system AI (no ELO)")

    # board-image
    p_bi = sub.add_parser("board-image", help="Generate board PNG image")
    p_bi.add_argument("--game-id", required=True, help="Game ID")
    p_bi.add_argument("--send-chat", metavar="CHAT_ID", default=None,
                      help="Send image to this Telegram chat_id via Bot API")

    # ai-move (single step for step-by-step practice)
    p_aimove = sub.add_parser("ai-move", help="Get AI hint and submit one move")
    p_aimove.add_argument("--game-id", required=True, help="Game ID")

    # telegram-setup
    p_tgsetup = sub.add_parser("telegram-setup", help="Save Telegram chat_id for board image sending")
    p_tgsetup.add_argument("--chat-id", required=True, help="Telegram chat ID")

    # stats
    sub.add_parser("stats", help="Show win/loss/draw statistics")

    # ai-hint
    p_hint = sub.add_parser("ai-hint", help="Get server AI move (fallback)")
    p_hint.add_argument("--game-id", required=True, help="Game ID")

    # strategy
    p_strat = sub.add_parser("strategy", help="Manage playing strategies")
    strat_sub = p_strat.add_subparsers(dest="strategy_cmd")

    strat_sub.add_parser("list", help="List all strategies")

    p_show = strat_sub.add_parser("show", help="Show strategy content")
    p_show.add_argument("name", nargs="?", default=None, help="Strategy name (default: active)")

    p_add = strat_sub.add_parser("add", help="Add a new strategy")
    p_add.add_argument("--name", required=True)
    p_add.add_argument("--content", required=True)

    p_upd = strat_sub.add_parser("update", help="Update existing strategy")
    p_upd.add_argument("--name", required=True)
    p_upd.add_argument("--content", required=True)

    p_del = strat_sub.add_parser("delete", help="Delete a strategy")
    p_del.add_argument("--name", required=True)

    p_use = strat_sub.add_parser("use", help="Set active strategy")
    p_use.add_argument("--name", required=True)

    p_think = strat_sub.add_parser("think", help="Get/set think time limit")
    p_think.add_argument("--seconds", type=int, default=None, help="Think time in seconds (5-30)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    cfg = load_config()

    if args.command == "get-turn":
        cmd_get_turn(args, cfg)
    elif args.command == "move":
        cmd_move(args, cfg)
    elif args.command == "heartbeat":
        cmd_heartbeat(args, cfg)
    elif args.command == "status":
        cmd_status(args, cfg)
    elif args.command == "save-token":
        cmd_save_token(args, cfg)
    elif args.command == "join-queue":
        cmd_join_queue(args, cfg)
    elif args.command == "leave-queue":
        cmd_leave_queue(args, cfg)
    elif args.command == "queue-status":
        cmd_queue_status(args, cfg)
    elif args.command == "set-games":
        n = args.n
        if n and n > 0:
            MAX_GAMES_FILE.write_text(str(n))
            print(f"SET_GAMES={n} (生效於下一局結束後)")
        else:
            MAX_GAMES_FILE.unlink(missing_ok=True)
            print("SET_GAMES=unlimited")
    elif args.command == "practice":
        cmd_practice(args, cfg)
    elif args.command == "board-image":
        cmd_board_image(args, cfg)
    elif args.command == "ai-move":
        cmd_ai_move(args, cfg)
    elif args.command == "telegram-setup":
        cmd_telegram_setup(args, cfg)
    elif args.command == "stats":
        cmd_stats(args, cfg)
    elif args.command == "play":
        cmd_play(args, cfg)
    elif args.command == "ai-hint":
        cmd_ai_hint(args, cfg)
    elif args.command == "strategy":
        if not args.strategy_cmd:
            p_strat.print_help()
            sys.exit(0)
        cmd_strategy(args, cfg)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
