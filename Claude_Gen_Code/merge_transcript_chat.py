#!/usr/bin/env python3
"""
merge_transcript_chat.py

Interleaves a Zoom chat log with a Zoom VTT transcript, producing a single
Markdown file where chat messages that arrived while a given speaker was
talking are displayed as indented, clearly-marked blockquotes at the end of
that speaker's utterance (before the next speaker begins).

Usage:
    python merge_transcript_chat.py <transcript.vtt> <chat.txt> <output.md>
        [-include-private-msgs] [-chat-subtract-time HH:MM:SS]

Options:
    -include-private-msgs
        By default, chat messages that Zoom marks as private (direct
        messages between two participants, rather than messages sent to
        Everyone) are excluded from the output. Pass this flag to include
        them instead.

    -chat-subtract-time HH:MM:SS
        Subtract this amount of time from every chat message timestamp
        before merging. Useful when the host started the recording some
        time after the meeting (and therefore the chat log) began, so the
        chat timestamps are otherwise ahead of the transcript timestamps.
        Example: -chat-subtract-time 06:30 subtracts 6 minutes 30 seconds
        from every chat timestamp. Resulting negative timestamps are
        clamped to 00:00:00.

Rules implemented:
  - Consecutive VTT cues from the same speaker are grouped into one
    "utterance" that runs until the next speaker starts (or the transcript
    ends).
  - Each utterance is prefixed with a single start-time timestamp
    (HH:MM:SS, taken from the first cue in the group). No other timestamps
    are shown within that utterance.
  - Chat messages whose timestamp falls within [utterance_start,
    next_utterance_start) are appended, indented, right after that
    utterance's text.
  - Any chat messages that arrive after the last transcript utterance ends
    are appended at the very end of the document under their own heading.
  - Chat messages are rendered as indented blockquotes with a distinct
    "💬" marker and bold sender name, so they're easy to visually
    distinguish from spoken content.
  - Private (direct message) chat messages are excluded by default; pass
    -include-private-msgs to include them.
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from typing import List, Optional


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------

@dataclass
class ChatMessage:
    time_str: str          # "HH:MM:SS" (possibly time-shifted for display)
    seconds: float         # normalized seconds-from-start (possibly shifted)
    sender: str
    text: str              # may be multi-line
    is_private: bool = False   # True if Zoom marked this as a private/DM


@dataclass
class Utterance:
    speaker: str
    start_seconds: float
    start_str: str          # HH:MM:SS
    lines: List[str] = field(default_factory=list)
    chats: List[ChatMessage] = field(default_factory=list)


# --------------------------------------------------------------------------
# Time helpers
# --------------------------------------------------------------------------

def hms_to_seconds(h: int, m: int, s: float) -> float:
    return h * 3600 + m * 60 + s


def parse_vtt_timestamp(ts: str) -> float:
    """Parse '00:01:23.456' -> seconds (float)."""
    h, m, s = ts.split(":")
    return hms_to_seconds(int(h), int(m), float(s))


def parse_chat_timestamp(ts: str) -> float:
    """Parse chat log timestamp, which may be 'MM:SS' or 'HH:MM:SS'."""
    parts = ts.split(":")
    if len(parts) == 2:
        m, s = parts
        return hms_to_seconds(0, int(m), float(s))
    elif len(parts) == 3:
        h, m, s = parts
        return hms_to_seconds(int(h), int(m), float(s))
    else:
        raise ValueError(f"Unrecognized timestamp format: {ts}")


def parse_offset_to_seconds(offset_str: str) -> float:
    """Parse a command-line time offset given as HH:MM:SS (or MM:SS) into
    seconds."""
    parts = offset_str.split(":")
    if len(parts) == 3:
        h, m, s = parts
        return hms_to_seconds(int(h), int(m), float(s))
    elif len(parts) == 2:
        m, s = parts
        return hms_to_seconds(0, int(m), float(s))
    elif len(parts) == 1:
        return float(parts[0])
    else:
        raise ValueError(
            f"Invalid -chat-subtract-time value: {offset_str!r}. "
            "Expected HH:MM:SS."
        )


def seconds_to_hms(total_seconds: float) -> str:
    total_seconds = int(round(total_seconds))
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


# --------------------------------------------------------------------------
# VTT parsing
# --------------------------------------------------------------------------

VTT_TIME_RE = re.compile(
    r"(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})"
)

def parse_vtt(path: str) -> List[Utterance]:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Normalize line endings, split into cue blocks separated by blank lines
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    blocks = content.split("\n\n")

    cues = []  # (start_seconds, speaker, text)
    for block in blocks:
        lines = [l for l in block.split("\n") if l.strip() != ""]
        if not lines:
            continue
        # Skip the WEBVTT header block
        if lines[0].strip().upper() == "WEBVTT":
            continue

        # Find the timing line within this block (first line might be a
        # cue index number)
        time_line_idx = None
        for i, line in enumerate(lines):
            if VTT_TIME_RE.search(line):
                time_line_idx = i
                break
        if time_line_idx is None:
            continue

        m = VTT_TIME_RE.search(lines[time_line_idx])
        start_ts = m.group(1)
        start_seconds = parse_vtt_timestamp(start_ts)

        text_lines = lines[time_line_idx + 1:]
        if not text_lines:
            continue
        full_text = " ".join(t.strip() for t in text_lines).strip()

        # Text is usually "Speaker Name: utterance text"
        speaker = "Unknown Speaker"
        utterance_text = full_text
        if ":" in full_text:
            possible_speaker, rest = full_text.split(":", 1)
            # Heuristic: treat as "Speaker: text" only if the speaker part
            # looks like a name (not overly long, no sentence punctuation)
            if len(possible_speaker) <= 60 and not any(
                p in possible_speaker for p in [".", "?", "!"]
            ):
                speaker = possible_speaker.strip()
                utterance_text = rest.strip()

        cues.append((start_seconds, speaker, utterance_text))

    # Group consecutive cues by same speaker into Utterances
    utterances: List[Utterance] = []
    for start_seconds, speaker, text in cues:
        if utterances and utterances[-1].speaker == speaker:
            utterances[-1].lines.append(text)
        else:
            utt = Utterance(
                speaker=speaker,
                start_seconds=start_seconds,
                start_str=seconds_to_hms(start_seconds),
            )
            utt.lines.append(text)
            utterances.append(utt)

    return utterances


# --------------------------------------------------------------------------
# Chat log parsing
# --------------------------------------------------------------------------

# A new chat message begins with a line like:
#   HH:MM:SS<TAB>Sender Name:<TAB>message text
# Message text itself may span multiple lines (e.g. "Replying to ..." quotes,
# multi-line links, etc.), so we detect new messages by this leading pattern
# and treat everything else as continuation lines.
CHAT_MSG_START_RE = re.compile(
    r"^(\d{1,2}:\d{2}(?::\d{2})?)\t([^\t]+):\t(.*)$"
)

# Zoom marks a chat message as a private/direct message by rendering the
# sender field as "Sender Name to Recipient Name (Direct Message)" or, in
# older exports, "Sender Name to Recipient Name(Privately)". Public
# messages sent to everyone just show the plain sender name.
PRIVATE_SENDER_RE = re.compile(
    r"^(?P<sender>.+?)\s+to\s+(?P<recipient>.+?)\s*\((?:Direct Message|Privately)\)\s*$",
    re.IGNORECASE,
)


def parse_chat(path: str, subtract_seconds: float = 0.0) -> List[ChatMessage]:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    content = content.replace("\r\n", "\n").replace("\r", "\n")
    raw_lines = content.split("\n")

    messages: List[ChatMessage] = []
    current: Optional[ChatMessage] = None

    for line in raw_lines:
        m = CHAT_MSG_START_RE.match(line)
        if m:
            # Flush previous message
            if current is not None:
                messages.append(current)
            time_str, sender_field, text = m.groups()
            seconds = parse_chat_timestamp(time_str)
            seconds = max(0.0, seconds - subtract_seconds)
            display_time_str = seconds_to_hms(seconds)

            is_private = False
            sender = sender_field.strip()
            priv_match = PRIVATE_SENDER_RE.match(sender)
            if priv_match:
                is_private = True
                sender = priv_match.group("sender").strip()

            current = ChatMessage(
                time_str=display_time_str,
                seconds=seconds,
                sender=sender,
                text=text.rstrip(),
                is_private=is_private,
            )
        else:
            # Continuation of the previous message (e.g. blank line inside
            # a "Replying to ..." quote, or a follow-up line of a link/post)
            if current is not None:
                if line.strip() == "" and current.text == "":
                    # avoid leading blank lines
                    continue
                if current.text:
                    current.text += "\n" + line
                else:
                    current.text = line
    if current is not None:
        messages.append(current)

    return messages


# --------------------------------------------------------------------------
# Merging
# --------------------------------------------------------------------------

def assign_chats_to_utterances(
    utterances: List[Utterance], chats: List[ChatMessage]
) -> List[ChatMessage]:
    """Assign each chat message to the utterance active at that time.
    Returns the list of leftover chat messages that occurred after the
    last utterance's start (i.e., after the meeting's spoken content
    effectively ended, based on transcript coverage) -- specifically,
    chats with timestamp >= end of the meeting (after final utterance
    and after the last cue's span) are returned separately if they fall
    after the final utterance's *last* content moment; but since we
    only have utterance start times, we treat "leftover" as chats whose
    timestamp is >= the start time of the LAST utterance's group end.
    Practically: any chat at or after the last utterance's start time
    that occurs after the transcript's very last cue time is leftover.
    """
    if not utterances:
        return list(chats)

    starts = [u.start_seconds for u in utterances]
    leftover: List[ChatMessage] = []

    for chat in chats:
        # Find the last utterance whose start_seconds <= chat.seconds
        idx = None
        for i, s in enumerate(starts):
            if s <= chat.seconds:
                idx = i
            else:
                break
        if idx is None:
            # Chat happened before the transcript's first utterance began;
            # attach to the first utterance anyway (edge case).
            utterances[0].chats.append(chat)
        else:
            utterances[idx].chats.append(chat)

    return leftover


def build_markdown(
    utterances: List[Utterance],
    leftover_chats: List[ChatMessage],
    title: str = "Meeting Transcript with Chat",
) -> str:
    out_lines = [f"# {title}", ""]

    for utt in utterances:
        out_lines.append(f"**[{utt.start_str}] {utt.speaker}:**")
        out_lines.append("")
        paragraph = " ".join(l for l in utt.lines if l)
        out_lines.append(paragraph)
        out_lines.append("")

        for chat in utt.chats:
            out_lines.append(render_chat_message(chat))
            out_lines.append("")

    if leftover_chats:
        out_lines.append("---")
        out_lines.append("")
        out_lines.append("## Chat messages after the meeting ended")
        out_lines.append("")
        for chat in leftover_chats:
            out_lines.append(render_chat_message(chat))
            out_lines.append("")

    return "\n".join(out_lines).rstrip() + "\n"


def render_chat_message(chat: ChatMessage) -> str:
    """Render a chat message as an indented, clearly-marked blockquote."""
    text_lines = chat.text.split("\n")
    rendered = [f"> 💬 **{chat.sender}** ({chat.time_str}): {text_lines[0]}"]
    for extra in text_lines[1:]:
        rendered.append(f"> {extra}" if extra.strip() else ">")
    return "\n".join(rendered)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Interleave a Zoom chat log with a Zoom VTT transcript into a "
            "single Markdown file."
        ),
        prefix_chars="-",
    )
    parser.add_argument("vtt_path", help="Path to the .vtt transcript file")
    parser.add_argument("chat_path", help="Path to the Zoom chat .txt file")
    parser.add_argument("out_path", help="Path to write the output .md file")
    parser.add_argument(
        "-include-private-msgs",
        dest="include_private_msgs",
        action="store_true",
        default=False,
        help=(
            "Include chat messages Zoom marked as private/direct "
            "messages. By default these are excluded."
        ),
    )
    parser.add_argument(
        "-chat-subtract-time",
        dest="chat_subtract_time",
        default=None,
        metavar="HH:MM:SS",
        help=(
            "Subtract this amount of time from every chat message "
            "timestamp before merging, to correct for the host starting "
            "the recording after the meeting/chat began."
        ),
    )
    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    subtract_seconds = 0.0
    if args.chat_subtract_time:
        try:
            subtract_seconds = parse_offset_to_seconds(args.chat_subtract_time)
        except ValueError as e:
            parser.error(str(e))

    utterances = parse_vtt(args.vtt_path)
    chats = parse_chat(args.chat_path, subtract_seconds=subtract_seconds)

    total_chat_count = len(chats)
    private_count = sum(1 for c in chats if c.is_private)

    if not args.include_private_msgs:
        chats = [c for c in chats if not c.is_private]

    leftover = assign_chats_to_utterances(utterances, chats)
    markdown = build_markdown(utterances, leftover)

    with open(args.out_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"Wrote {args.out_path}")
    print(f"  {len(utterances)} speaker utterances")
    print(f"  {total_chat_count} chat messages found ({private_count} private)")
    print(f"  {len(chats)} chat messages included in output")
    print(f"  {len(leftover)} leftover chat messages after final utterance")
    if subtract_seconds:
        print(f"  chat timestamps shifted back by {subtract_seconds:.0f}s")


if __name__ == "__main__":
    main()
