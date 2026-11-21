#!/usr/bin/env python3
"""Speak text aloud on macOS."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

HOME = Path.home()
APP_DIR = HOME / ".local/share/voice-speak"
STATE_DIR = HOME / ".local/state/voice-speak"
LOG_FILE = STATE_DIR / "voice-speak.log"
PID_FILE = STATE_DIR / "player.pid"
QUEUE_PID_FILE = STATE_DIR / "queue.pid"
CONFIG_FILE = APP_DIR / "config.json"
TMP_DIR = Path("/tmp")

DEFAULTS = {
    "engine": "auto",
    "edge_voice_zh": "zh-CN-XiaoxiaoNeural",
    "edge_voice_en": "en-US-AriaNeural",
    "say_voice_zh": "Tingting",
    "say_voice_en": "Samantha",
    "edge_rate": "+8%",
    "say_rate": 190,
    "max_chars": 0,
    "queue_chunk_chars": 200,
    "timeout_seconds": 8,
}

CURRENT_PROCESS: subprocess.Popen | None = None
CURRENT_AUDIO: Path | None = None


def ensure_dirs() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    config = dict(DEFAULTS)
    try:
        config.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
    except Exception:
        pass
    return config


def log(message: str) -> None:
    ensure_dirs()
    try:
        if LOG_FILE.exists() and LOG_FILE.stat().st_size > 512_000:
            LOG_FILE.replace(LOG_FILE.with_suffix(".log.1"))
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(f"{datetime.now().isoformat(timespec='seconds')} {message}\n")
    except Exception:
        pass


def clean_text(text: str, max_chars: int = 0) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.M)
    text = re.sub(r"^\s*\d+[.)]\s+", "", text, flags=re.M)
    text = re.sub(r"(\*\*|__|~~|\*|_)", "", text)
    text = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]", "", text)
    text = re.sub(r"[\t ]+", " ", text)
    text = re.sub(r"\s*\n\s*", " ", text)
    text = text.strip(" \n-—")

    if max_chars and len(text) > max_chars:
        head = text[:max_chars]
        cut = max(
            head.rfind("。"),
            head.rfind("！"),
            head.rfind("？"),
            head.rfind("；"),
            head.rfind("."),
            head.rfind("!"),
            head.rfind("?"),
        )
        if cut >= max_chars * 0.45:
            text = head[: cut + 1]
        else:
            text = head.rstrip("，,、;；:： ") + "……"
    return text


def has_cjk(text: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", text))


def normalize_edge_rate(value: str) -> str:
    value = str(value).strip()
    if re.fullmatch(r"\d+%?", value):
        return f"+{value}"
    return value


def normalize_say_rate(value: str) -> int:
    match = re.search(r"-?\d+", str(value))
    return int(match.group()) if match else 190


def resolve_voice(config: dict, engine: str, text: str, explicit: str | None) -> str:
    if explicit:
        return explicit
    env_voice = os.environ.get("VOICE_SPEAK_VOICE") or os.environ.get("VOICE_NOTIFY_VOICE")
    if env_voice:
        return env_voice
    if has_cjk(text):
        key = "edge_voice_zh" if engine == "edge" else "say_voice_zh"
    else:
        key = "edge_voice_en" if engine == "edge" else "say_voice_en"
    return config[key]


def process_args(pid: int) -> str:
    try:
        result = subprocess.run(
            ["/bin/ps", "-p", str(pid), "-o", "args="],
            capture_output=True,
            text=True,
            timeout=2,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def stop_queue() -> None:
    try:
        pid = int(QUEUE_PID_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        return
    args = process_args(pid)
    if "voice_speak.py" in args or "voice-speak" in args:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        for _ in range(30):
            if not process_args(pid):
                break
            time.sleep(0.1)
    QUEUE_PID_FILE.unlink(missing_ok=True)


def stop_playback() -> None:
    stop_queue()
    try:
        pid = int(PID_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        return
    args = process_args(pid)
    if "afplay" in args:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    PID_FILE.unlink(missing_ok=True)


def make_temp_path(suffix: str) -> Path:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix="voice-speak-", suffix=suffix, dir=str(TMP_DIR))
    os.close(descriptor)
    return Path(name)


async def edge_save(text: str, voice: str, rate: str, target: Path) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(str(target))


def synth_edge(text: str, voice: str, rate: str, timeout: int) -> Path:
    global CURRENT_AUDIO
    target = make_temp_path(".mp3")
    CURRENT_AUDIO = target
    try:
        asyncio.run(asyncio.wait_for(edge_save(text, voice, rate, target), timeout=timeout))
        if target.stat().st_size <= 0:
            raise RuntimeError("empty audio file")
        return target
    except Exception:
        target.unlink(missing_ok=True)
        CURRENT_AUDIO = None
        raise


def synth_say(text: str, voice: str, rate: int) -> Path:
    global CURRENT_AUDIO
    target = make_temp_path(".aiff")
    CURRENT_AUDIO = target
    try:
        subprocess.run(
            ["/usr/bin/say", "-v", voice, "-r", str(rate), "-o", str(target), text],
            check=True,
            timeout=15,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return target
    except Exception:
        target.unlink(missing_ok=True)
        CURRENT_AUDIO = None
        raise


def worker_stop(signum, frame) -> None:
    global CURRENT_PROCESS, CURRENT_AUDIO
    if CURRENT_PROCESS is not None and CURRENT_PROCESS.poll() is None:
        try:
            CURRENT_PROCESS.terminate()
        except Exception:
            pass
    if CURRENT_AUDIO is not None:
        try:
            CURRENT_AUDIO.unlink(missing_ok=True)
        except Exception:
            pass
    raise SystemExit(0)


def play_blocking(audio: Path) -> None:
    global CURRENT_PROCESS, CURRENT_AUDIO
    CURRENT_AUDIO = audio
    process = subprocess.Popen(
        ["/usr/bin/afplay", str(audio)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )
    CURRENT_PROCESS = process
    try:
        PID_FILE.write_text(str(process.pid), encoding="utf-8")
    except Exception:
        pass
    try:
        code = process.wait()
        if code != 0:
            log(f"afplay exited {code}")
    finally:
        CURRENT_PROCESS = None
        PID_FILE.unlink(missing_ok=True)
        audio.unlink(missing_ok=True)
        CURRENT_AUDIO = None


def split_long_sentence(sentence: str, limit: int) -> list[str]:
    pieces = re.split(r"(?<=[，,、：:])", sentence)
    result: list[str] = []
    buffer = ""
    for piece in pieces:
        if len(piece) > limit:
            if buffer:
                result.append(buffer)
                buffer = ""
            for index in range(0, len(piece), limit):
                result.append(piece[index : index + limit])
        elif len(buffer) + len(piece) > limit:
            if buffer:
                result.append(buffer)
            buffer = piece
        else:
            buffer += piece
    if buffer:
        result.append(buffer)
    return [item.strip() for item in result if item.strip()]


def chunk_text(text: str, limit: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if limit <= 0 or len(text) <= limit:
        return [text]
    sentences = [
        item.strip()
        for item in re.split(r"(?<=[。！？.!?；;\n])", text)
        if item.strip()
    ]
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(split_long_sentence(sentence, limit))
        elif len(current) + len(sentence) > limit:
            if current:
                chunks.append(current)
            current = sentence
        else:
            current += sentence
    if current:
        chunks.append(current)
    return [item for item in chunks if item.strip()]


def run_worker(job_path: Path) -> int:
    ensure_dirs()
    signal.signal(signal.SIGTERM, worker_stop)
    signal.signal(signal.SIGINT, worker_stop)
    try:
        job = json.loads(job_path.read_text(encoding="utf-8"))
    except Exception as exc:
        log(f"worker job read failed: {exc!r}")
        job_path.unlink(missing_ok=True)
        return 1
    job_path.unlink(missing_ok=True)

    chunks = job.get("chunks") or []
    engine = job.get("engine", "edge")
    edge_voice = job.get("edge_voice", "")
    say_voice = job.get("say_voice", "")
    edge_rate = job.get("edge_rate", "+8%")
    say_rate = int(job.get("say_rate", 190))
    timeout = int(job.get("timeout", 8))
    edge_enabled = engine in ("edge", "auto")
    failures = 0

    try:
        QUEUE_PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    except Exception:
        pass

    try:
        for chunk in chunks:
            audio = None
            if edge_enabled:
                try:
                    audio = synth_edge(chunk, edge_voice, edge_rate, timeout)
                except Exception as exc:
                    log(f"edge failed: {exc!r}; falling back to say")
                    edge_enabled = False
            if audio is None:
                try:
                    audio = synth_say(chunk, say_voice, say_rate)
                except Exception as exc:
                    log(f"say failed: {exc!r}")
                    failures += 1
                    continue
            play_blocking(audio)
        log(f"queue finished chunks={len(chunks)} failures={failures}")
        return 0 if failures == 0 else 1
    finally:
        QUEUE_PID_FILE.unlink(missing_ok=True)


def spawn_worker(job: dict, wait: bool) -> int:
    ensure_dirs()
    job_path = make_temp_path(".json")
    job_path.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    try:
        process = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--worker", str(job_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
    except Exception as exc:
        log(f"worker spawn failed: {exc!r}")
        job_path.unlink(missing_ok=True)
        return 1
    if wait:
        code = process.wait()
        QUEUE_PID_FILE.unlink(missing_ok=True)
        return code
    return 0


def main(argv: list[str] | None = None) -> int:
    config = load_config()
    parser = argparse.ArgumentParser(prog="voice-speak", description="Speak text aloud on macOS.")
    parser.add_argument("text", nargs="?", help="Text to speak, or - to read stdin")
    parser.add_argument("--file", help="Read text from a UTF-8 file")
    parser.add_argument(
        "--engine",
        choices=["auto", "edge", "say"],
        default=os.environ.get("VOICE_SPEAK_ENGINE") or os.environ.get("VOICE_NOTIFY_ENGINE") or config["engine"],
        help="auto tries Edge then Apple say; say is offline and immediate",
    )
    parser.add_argument("--voice", help="Explicit voice name")
    parser.add_argument("--rate", help="Speech rate, e.g. +8%% for Edge or 190 for say")
    parser.add_argument("--max-chars", type=int, default=config["max_chars"], help="0 means no truncation")
    parser.add_argument("--wait", action="store_true", help="Wait until the whole queue finishes")
    parser.add_argument("--stop", action="store_true", help="Stop current playback and queue")
    parser.add_argument("--dry-run", action="store_true", help="Print text, voice, and chunk count without speaking")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.worker:
        return run_worker(Path(args.worker))

    ensure_dirs()

    if args.stop:
        stop_playback()
        log("stopped playback")
        return 0

    raw = args.text
    if args.file:
        raw = Path(args.file).expanduser().read_text(encoding="utf-8")
    if raw == "-":
        raw = sys.stdin.read()
    if not raw:
        parser.error("text is required")

    text = clean_text(raw, args.max_chars)
    if not text:
        return 0

    chunks = chunk_text(text, int(config.get("queue_chunk_chars", 200)))
    planned = "edge" if args.engine in ("auto", "edge") else "say"
    edge_voice = resolve_voice(config, "edge", text, args.voice)
    say_voice = resolve_voice(config, "say", text, args.voice)
    planned_voice = edge_voice if planned == "edge" else say_voice

    if args.dry_run:
        print(
            json.dumps(
                {
                    "text": text,
                    "engine": planned,
                    "voice": planned_voice,
                    "chunks": len(chunks),
                },
                ensure_ascii=False,
            )
        )
        return 0

    job = {
        "chunks": chunks,
        "engine": planned,
        "edge_voice": edge_voice,
        "say_voice": say_voice,
        "edge_rate": normalize_edge_rate(
            args.rate or os.environ.get("VOICE_NOTIFY_RATE") or config["edge_rate"]
        ),
        "say_rate": normalize_say_rate(
            args.rate or os.environ.get("VOICE_NOTIFY_RATE") or config["say_rate"]
        ),
        "timeout": config["timeout_seconds"],
    }

    stop_playback()
    code = spawn_worker(job, args.wait)
    if code != 0 and not args.quiet:
        print(f"voice-speak: playback failed with exit code {code}", file=sys.stderr)
    if not args.wait:
        log(f"queued chunks={len(chunks)} text={text[:200]}")
    return code


if __name__ == "__main__":
    sys.exit(main())
