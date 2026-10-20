#!/usr/bin/env python3
"""
vtt_to_transcript.py

Convert a YouTube auto-generated .vtt caption file into a clean,
timestamped Markdown transcript, split into turns wherever the
captions mark a speaker change (the ">>" symbol). Optionally merge
in a Zoom-style chat log (e.g. "meeting_saved_new_chat.txt"), with
each chat message indented under the transcript turn whose time
window it falls inside.

YouTube's auto-captions do NOT identify who is speaking -- they only
mark that a different voice was detected than in the previous line.
This script reconstructs the underlying dialogue (undoing the
rolling/duplicated caption cues YouTube uses) and splits it into
turns at each ">>" marker, tagging each turn with the timestamp of
its first word. It does not attempt to guess speaker identity.

BASIC USAGE (transcript only):
    python3 vtt_to_transcript.py input.vtt [-o output.md]

MERGING IN CHAT:
    python3 vtt_to_transcript.py input.vtt \\
        --chat meeting_saved_new_chat.txt \\
        --meeting-start "2026-08-03 11:43:00" \\
        [--chat-offset 15] \\
        [-o output.md]

    --meeting-start is the real-world (wall-clock) date/time that
    corresponds to 00:00:00 in the video/transcript. Chat log entries
    are timestamped in wall-clock time, so this anchor is required to
    know where each chat message falls on the video's timeline.
    A good starting guess is the timestamp of the very first chat
    message, or the meeting's scheduled start time.

    --chat-offset lets you nudge the alignment after the fact, without
    re-guessing --meeting-start. It's added (in seconds) to every chat
    message's computed video-time position. Positive shifts chat later
    (as if it happened further into the video); negative shifts it
    earlier. Use this to correct for clock drift between the chat log
    and the recording, or an imprecise --meeting-start guess.
"""

import argparse
import html
import re
import sys
from datetime import datetime
from pathlib import Path

TS_LINE_RE = re.compile(r"^(\d\d:\d\d:\d\d\.\d\d\d) --> ")
WORD_TAG_RE = re.compile(r"<(\d\d:\d\d:\d\d\.\d\d\d)><c>([^<]*)</c>")
CHAT_HEADER_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+From\s+(.+?)\s+to\s+Everyone:\s*$"
)
CHAT_TS_FORMAT = "%Y-%m-%d %H:%M:%S"


# --------------------------------------------------------------------------
# VTT parsing / transcript reconstruction
# --------------------------------------------------------------------------

def parse_last_line(last, block_start):
    """Parse the final text line of a cue block into (word, timestamp) pairs."""
    out = []
    first_tag_idx = last.find("<")
    leading = last[:first_tag_idx] if first_tag_idx != -1 else last
    leading = html.unescape(leading).strip()
    if leading:
        for w in leading.split():
            out.append((w, block_start))
    for tmatch in WORD_TAG_RE.finditer(last):
        wts = tmatch.group(1)
        wtext = html.unescape(tmatch.group(2)).strip()
        if wtext:
            for w in wtext.split():
                out.append((w, wts))
    return out


def build_word_timeline(vtt_text):
    """Deduplicate YouTube's rolling caption cues into a single word timeline."""
    blocks = vtt_text.split("\n\n")
    emitted_plain = []
    timeline = []

    for block in blocks:
        lines = block.strip("\n").split("\n")
        if not lines or not TS_LINE_RE.match(lines[0]):
            continue
        start = TS_LINE_RE.match(lines[0]).group(1)
        text_lines = lines[1:]
        if not text_lines:
            continue
        last = text_lines[-1]
        if last.strip() == "":
            continue

        cur = parse_last_line(last, start)
        cur_plain = [w for w, _ in cur]

        max_k = min(len(emitted_plain), len(cur_plain))
        k = 0
        for cand in range(max_k, -1, -1):
            if cand == 0:
                k = 0
                break
            if emitted_plain[-cand:] == cur_plain[:cand]:
                k = cand
                break

        for w, ts in cur[k:]:
            emitted_plain.append(w)
            timeline.append((w, ts))

    return timeline


def ts_to_seconds(ts):
    h, m, s = ts.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def split_into_turns(timeline):
    """Split the word timeline into utterances at each '>>' speaker-change marker.

    Returns a list of dicts: {"start": seconds, "text": str}
    """
    turns = []
    cur_words = []
    cur_start = None

    def flush():
        if cur_words:
            turns.append({"start": ts_to_seconds(cur_start), "text": " ".join(cur_words).strip()})

    for w, ts in timeline:
        if w == ">>":
            flush()
            cur_words.clear()
            cur_start = None
            continue
        if cur_start is None:
            cur_start = ts
        cur_words.append(w)
    flush()
    return turns


def fmt_ts(total_seconds):
    """Format a number of seconds as H:MM:SS (or MM:SS if under an hour)."""
    total_seconds = max(0, int(total_seconds))
    h, rem = divmod(total_seconds, 3600)
    m, s = divmod(rem, 60)
    if h == 0:
        return f"{m:02d}:{s:02d}"
    return f"{h}:{m:02d}:{s:02d}"


# --------------------------------------------------------------------------
# Chat log parsing
# --------------------------------------------------------------------------

def parse_chat_file(path):
    """Parse a Zoom-style chat log into a list of dicts:
    {"time": datetime, "sender": str, "text": str}
    """
    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    entries = []
    cur = None
    body_lines = []

    def flush():
        if cur is not None:
            text = " ".join(l for l in body_lines if l.strip())
            entries.append({"time": cur[0], "sender": cur[1], "text": text})

    for line in lines:
        m = CHAT_HEADER_RE.match(line)
        if m:
            flush()
            dt = datetime.strptime(m.group(1), CHAT_TS_FORMAT)
            sender = m.group(2).strip()
            cur = (dt, sender)
            body_lines = []
        else:
            if cur is not None:
                body_lines.append(line.strip("\t").strip())
    flush()
    return entries


# --------------------------------------------------------------------------
# Merging chat into transcript turns
# --------------------------------------------------------------------------

def attach_chat_to_turns(turns, chat_entries, meeting_start, offset_seconds=0.0):
    """Assign each chat message to the transcript turn whose time window
    it falls into, based on wall-clock alignment.

    turns: list of {"start": seconds, "text": str}, sorted by start.
    chat_entries: list of {"time": datetime, "sender": str, "text": str}
    meeting_start: datetime corresponding to video time 00:00:00
    offset_seconds: added to each chat message's computed video-time
        position, to manually nudge alignment forward (+) or back (-).
    """
    for t in turns:
        t["chat"] = []

    if not turns:
        return turns

    last_idx = len(turns) - 1

    for entry in chat_entries:
        video_time = (entry["time"] - meeting_start).total_seconds() + offset_seconds

        # Clamp messages that fall before the first turn or after the last one.
        if video_time <= turns[0]["start"]:
            idx = 0
        elif video_time >= turns[last_idx]["start"]:
            idx = last_idx
        else:
            # Find the turn whose window [start, next_start) contains video_time.
            idx = last_idx
            for i in range(last_idx):
                if turns[i]["start"] <= video_time < turns[i + 1]["start"]:
                    idx = i
                    break

        turns[idx]["chat"].append((video_time, entry["sender"], entry["text"]))

    for t in turns:
        t["chat"].sort(key=lambda c: c[0])

    return turns


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

def write_markdown(turns, output_path, has_chat):
    lines = ["# Transcript\n"]
    for t in turns:
        lines.append(f"- **[{fmt_ts(t['start'])}]** {t['text']}")
        if has_chat:
            for video_time, sender, text in t.get("chat", []):
                lines.append(f"    - \U0001F4AC [{fmt_ts(video_time)}] **{sender}:** {text}")
    Path(output_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Convert a YouTube auto-generated .vtt file to a Markdown "
        "transcript, optionally merging in a Zoom-style chat log."
    )
    parser.add_argument("vtt_file", help="Path to the .vtt caption file")
    parser.add_argument("-o", "--output", help="Output .md path (default: <input>_transcript.md)")
    parser.add_argument("--chat", help="Path to a Zoom-style chat log file to merge in")
    parser.add_argument(
        "--meeting-start",
        help='Wall-clock date/time matching video 00:00:00, e.g. "2026-08-03 11:43:00". '
        "Required if --chat is given.",
    )
    parser.add_argument(
        "--chat-offset",
        type=float,
        default=0.0,
        help="Seconds to shift all chat timestamps by (+ later, - earlier), "
        "for manually fine-tuning alignment. Default: 0.",
    )
    args = parser.parse_args()

    if args.chat and not args.meeting_start:
        parser.error("--meeting-start is required when using --chat")

    vtt_path = Path(args.vtt_file)
    output_path = Path(args.output) if args.output else vtt_path.with_name(vtt_path.stem + "_transcript.md")

    vtt_text = vtt_path.read_text(encoding="utf-8")
    timeline = build_word_timeline(vtt_text)
    turns = split_into_turns(timeline)

    has_chat = bool(args.chat)
    if has_chat:
        chat_entries = parse_chat_file(args.chat)
        try:
            meeting_start = datetime.strptime(args.meeting_start, CHAT_TS_FORMAT)
        except ValueError:
            print(
                f'Error: --meeting-start must look like "2026-08-03 11:43:00", '
                f"got {args.meeting_start!r}",
                file=sys.stderr,
            )
            sys.exit(1)
        turns = attach_chat_to_turns(turns, chat_entries, meeting_start, args.chat_offset)

    write_markdown(turns, output_path, has_chat)

    n_chat = sum(len(t.get("chat", [])) for t in turns) if has_chat else 0
    msg = f"Wrote {len(turns)} turns"
    if has_chat:
        msg += f" and {n_chat} chat messages"
    msg += f" to {output_path}"
    print(msg)


if __name__ == "__main__":
    main()
