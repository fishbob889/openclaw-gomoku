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

COL_LABELS = "ABCDEFGHIJKLMNO"

DEFAULT_CONFIG = {
    "skill_token": "",
    "api_base": "https://fishbob-openclaw-api.fly.dev",
    "think_seconds": 10,
    "active_strategy": "",
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
            val = board[r][c] if board and r < len(board) and c < len(board[r]) else 0
            if last_move_pos and last_move_pos.get("row") == r and last_move_pos.get("col") == c:
                cells.append(LAST)
            elif val == 1:
                cells.append(BLACK)
            elif val == 2:
                cells.append(WHITE)
            else:
                cells.append(EMPTY)
        lines.append(row_label + " ".join(cells))

    return "\n".join(lines)


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

    # Last move
    last_move_pos = None
    last_move_coord = ""
    if moves:
        lm = moves[-1]
        pos = lm.get("position") or lm
        if isinstance(pos, dict) and "row" in pos:
            last_move_pos = pos
            last_move_coord = pos_to_coord(pos["row"], pos["col"])

    # My color
    my_color = current_player  # 'black' or 'white'

    # Count moves
    move_count = len(moves)
    turn_number = move_count + 1

    # Output for AI
    print(f"GAME_ID={game_id}")
    print(f"MY_COLOR={my_color}")
    print(f"TURN={turn_number}")
    print(f"LAST_MOVE={last_move_coord if last_move_coord else 'none'}")
    print(f"BLACK={player_names.get('black', 'Black')}")
    print(f"WHITE={player_names.get('white', 'White')}")
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
    api = get_api(cfg)
    headers = get_headers(cfg)
    headers["Content-Type"] = "application/json"

    ai_model = getattr(args, "ai_model", None) or "gomoku.py"

    try:
        resp = requests.post(
            f"{api}/skill/heartbeat",
            json={"ai_model": ai_model},
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


def cmd_save_token(args, cfg):
    """Save skill token to config."""
    token = args.token.strip()
    cfg["skill_token"] = token
    save_config(cfg)
    print(f"TOKEN_SAVED=ok")
    print(f"Token saved to {CONFIG_FILE}")


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
