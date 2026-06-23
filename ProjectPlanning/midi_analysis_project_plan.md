# Wish Prompt to Claude Sonnet 4.6

- I have a directory with subdirectories that contain MIDI files.  I want to understand what is in each MIDI file by using Clojure data structures to store high level information about their contents.  I am interested in the text meta event data as a starting point, but may be interested in doing future analysis of chord progressions and harmonic structure of the tracks in the MIDI files.  I also want a utility to convert the Type 1 MIDI files to Type 0 MIDI files by creating new files with the letter Z as a prefix to the filename in the same directory.  Please write a project plan for this project, focusing on the analysis of the best data structures to represent the desired information.

# Response: 
Here's a summary of the key decisions in the plan:

**Data structure philosophy.** Plain Clojure maps with namespaced keywords (`:midi/`, `:meta/`, `:note/`, `:chord/`) throughout — no records or types. This keeps everything transparent at the REPL, diffable, and ready for `clojure.spec` later. Every event carries both `:event/delta-ticks` (as stored in the file, needed for serialisation) and `:event/abs-ticks` (accumulated from track start, needed for sorting and duration math).

**Two-pass design.** Pass 1 is a pure binary parser that builds the raw map tree. Pass 2 is an optional enrichment step that walks the conductor track's tempo events and annotates every event with `:event/abs-seconds`. Keeping them separate means you can use the parser output without caring about wall-clock time.

**Text meta events** get a uniform envelope: `:meta/type` as a keyword (`:track-name`, `:lyric`, `:marker`, etc.), `:meta/raw-type` as the original byte for round-tripping, and `:meta/text` as a decoded string. A `:midi/meta-summary` map is assembled after parsing to give a rolled-up view across all tracks — answering "what is the key / tempo / track names of this file?" without walking the whole structure.

**Harmonic analysis path.** The plan lays out the progression: note events → NoteOn/Off pairing → note objects with durations → chord snapshots (all pitches active at each boundary) → chord labeling → Roman numeral analysis. Each step builds on the last and can be added incrementally in Phase 4.

**Type 1 → Type 0 conversion** is a merge-and-stable-sort on `:event/abs-ticks` across all tracks, followed by delta-time recomputation and binary re-serialisation to a `Z`-prefixed file.

The biggest open question worth deciding early is **overlapping notes on the same pitch/channel** — a stack-based pairing strategy is the most defensible for real-world MIDI files.


# MIDI Analysis Project Plan
## Clojure-Based MIDI Inspection, Data Modeling & Format Conversion

---

## 1. Project Overview

This project builds a Clojure library/tool that:

1. **Scans** a directory tree for MIDI files
2. **Parses** each file into rich Clojure data structures, starting with text meta events
3. **Lays groundwork** for future harmonic/chord analysis
4. **Converts** Type 1 (multi-track) MIDI files to Type 0 (single-track) files, writing them with a `Z` prefix in the same directory

---

## 2. MIDI Background: What We're Modeling

### MIDI File Types
| Type | Description |
|------|-------------|
| **Type 0** | Single track; all channels merged into one MTrk chunk |
| **Type 1** | Multiple synchronous tracks; most common for sequenced music |
| **Type 2** | Multiple independent patterns (rare, not targeted here) |

### Key Concepts
- **Tick** — raw time unit; meaning depends on the file's `ticks-per-beat` (PPQ) header value
- **Delta time** — ticks since the *previous* event in the same track
- **Absolute time** — accumulated ticks from track start (computed, not stored in file)
- **Meta events** — non-audio metadata: tempo, time signature, key signature, track name, lyrics, markers, etc.
- **Channel messages** — NoteOn, NoteOff, ControlChange, ProgramChange, etc.
- **SysEx events** — vendor-specific; mostly ignored for this analysis

---

## 3. Data Structure Design

### Design Principles
- Use **plain Clojure maps and vectors** — no defrecord/deftype unless performance demands it; maps are easier to inspect at the REPL
- **Namespaced keywords** (`:midi/`, `:meta/`, `:note/`, `:chord/`) to avoid collisions and enable spec validation later
- **Absolute ticks** stored alongside delta ticks so downstream analysis never has to re-accumulate
- **Immutable** throughout; transformations return new structures

---

### 3.1 Top-Level File Map

```clojure
{:midi/path          "/path/to/file.mid"       ; java.nio.Path or string
 :midi/filename      "sonata.mid"
 :midi/type          1                          ; 0, 1, or 2
 :midi/track-count   4
 :midi/ticks-per-beat 480                       ; PPQ (pulses per quarter note)
 :midi/tracks        [ <track-map> ... ]        ; vector, one per MTrk chunk
 :midi/meta-summary  <meta-summary-map>         ; rolled-up view across all tracks
 :midi/duration-ticks 184320                    ; total length in ticks (derived)
 }
```

**Why a `:midi/meta-summary`?** In Type 1 files, tempo and time-signature events typically live only in track 0 (the "conductor track"), while track names and lyrics appear in later tracks. A rolled-up summary lets callers answer "what is the key of this file?" without walking all tracks.

---

### 3.2 Track Map

```clojure
{:track/index         0                    ; 0-based position in file
 :track/label         "Conductor"          ; derived: name meta event if present
 :track/event-count   312
 :track/events        [ <event-map> ... ]  ; all events, in order
 :track/meta-events   [ <event-map> ... ]  ; filtered view: only meta events
 :track/note-events   [ <event-map> ... ]  ; filtered view: NoteOn / NoteOff
 :track/duration-ticks 184320
 }
```

Filtered views (`:track/meta-events`, `:track/note-events`) are **derived** with `filterv` at parse time and stored for fast access without re-scanning.

---

### 3.3 Event Map (all event types share a common envelope)

```clojure
{:event/type         :meta              ; :meta | :note-on | :note-off
                                        ; :control-change | :program-change
                                        ; :pitch-bend | :sysex | :channel-pressure
 :event/delta-ticks  0                  ; as stored in file
 :event/abs-ticks    0                  ; accumulated from track start
 :event/abs-seconds  0.0                ; derived from tempo map (added in pass 2)
 ;; --- type-specific keys below ---
 }
```

**Pass 1** builds the raw structure with ticks only. **Pass 2** walks the conductor track's tempo events and annotates every event with `:event/abs-seconds`. This separation keeps parsing simple and makes the second pass optional.

---

### 3.4 Meta Event Subtypes

All meta events extend the common envelope. The `:meta/type` keyword identifies the subtype.

#### Text-Class Meta Events

```clojure
;; Covers: Text (0x01), Copyright (0x02), Track Name (0x03),
;;         Instrument Name (0x04), Lyric (0x05), Marker (0x06), Cue Point (0x07)

{:event/type     :meta
 :meta/type      :track-name            ; keyword, see table below
 :meta/raw-type  0x03                   ; original byte, preserved for round-tripping
 :meta/text      "Piano"                ; decoded string (UTF-8 or Latin-1)
 :event/delta-ticks 0
 :event/abs-ticks   0}
```

| `:meta/type` keyword | Hex | Meaning |
|---|---|---|
| `:text` | 0x01 | General text annotation |
| `:copyright` | 0x02 | Copyright notice |
| `:track-name` | 0x03 | Track / sequence name |
| `:instrument-name` | 0x04 | Instrument description |
| `:lyric` | 0x05 | Lyric syllable |
| `:marker` | 0x06 | Rehearsal marker (e.g. "Verse 1") |
| `:cue-point` | 0x07 | Cue point label |

#### Tempo Event

```clojure
{:event/type        :meta
 :meta/type         :set-tempo
 :meta/raw-type     0x51
 :meta/uspq         500000              ; microseconds per quarter note
 :meta/bpm          120.0               ; derived: (/ 60000000.0 uspq)
 :event/delta-ticks 0
 :event/abs-ticks   0}
```

Tempo events form a **tempo map** (see §3.6) used to convert ticks → seconds.

#### Time Signature Event

```clojure
{:event/type           :meta
 :meta/type            :time-signature
 :meta/raw-type        0x58
 :meta/numerator       4
 :meta/denominator     4                ; stored as power of 2 in file; decoded here
 :meta/clocks-per-click 24
 :meta/32nds-per-quarter 8
 :event/delta-ticks    0
 :event/abs-ticks      0}
```

#### Key Signature Event

```clojure
{:event/type    :meta
 :meta/type     :key-signature
 :meta/raw-type 0x59
 :meta/sharps   -1                      ; negative = flats; range -7..+7
 :meta/mode     :major                  ; :major or :minor
 :meta/key-name "F major"               ; derived human-readable label
 :event/delta-ticks 0
 :event/abs-ticks   0}
```

#### End of Track

```clojure
{:event/type    :meta
 :meta/type     :end-of-track
 :meta/raw-type 0x7F
 :event/delta-ticks <n>
 :event/abs-ticks   <n>}
```

---

### 3.5 Note Events (foundation for future harmonic analysis)

```clojure
{:event/type       :note-on            ; or :note-off
 :event/delta-ticks 240
 :event/abs-ticks   4320
 :event/abs-seconds 2.25               ; filled in pass 2
 :note/channel     0                   ; 0–15
 :note/pitch       60                  ; MIDI note number; 60 = middle C
 :note/pitch-name  "C4"                ; derived
 :note/velocity    80                  ; 0 = note-off if type is :note-on
 }
```

NoteOn with velocity 0 is normalised to `:note-off` at parse time (common MIDI idiom).

---

### 3.6 Derived Structures for Future Analysis

These are not produced by the parser directly but are the natural next step.

#### Tempo Map (vector, sorted by abs-ticks)

```clojure
[ {:tempo/abs-ticks 0      :tempo/uspq 500000 :tempo/bpm 120.0}
  {:tempo/abs-ticks 9600   :tempo/uspq 400000 :tempo/bpm 150.0}
  ... ]
```

Used to convert any abs-tick value to wall-clock seconds via piecewise linear interpolation.

#### Note-On/Off Pairing → Note Objects

```clojure
{:note/pitch        60
 :note/pitch-name   "C4"
 :note/channel      0
 :note/on-ticks     0
 :note/off-ticks    480
 :note/duration-ticks 480
 :note/on-seconds   0.0
 :note/off-seconds  0.5
 :note/velocity     80}
```

Pairing is channel-and-pitch scoped. Ambiguous overlaps (same pitch, same channel, second NoteOn before NoteOff) are handled with a stack per `[channel pitch]` key.

#### Chord Snapshot (for harmonic analysis)

```clojure
{:chord/abs-ticks    0
 :chord/abs-seconds  0.0
 :chord/pitches      [60 64 67]          ; sorted MIDI note numbers
 :chord/pitch-names  ["C4" "E4" "G4"]
 :chord/pitch-classes #{0 4 7}           ; mod-12 set
 :chord/label        "C major"           ; optional: from chord-recognition pass
 :chord/roman        "I"                 ; optional: relative to key
 }
```

Chord snapshots are computed by scanning note objects and collecting all pitches active at each NoteOn/NoteOff boundary — a "piano roll slice" approach.

---

### 3.7 Meta Summary Map

A rolled-up view across all tracks in a file, computed after parsing:

```clojure
{:meta/track-names      ["Conductor" "Piano" "Bass" "Drums"]
 :meta/markers          [{:meta/text "Intro" :event/abs-ticks 0}
                         {:meta/text "Verse" :event/abs-ticks 3840} ...]
 :meta/lyrics           ["Hel-" "lo" "world" ...]
 :meta/tempo-changes    [ <tempo-map-entries> ]
 :meta/initial-bpm      120.0
 :meta/time-signatures  [ <time-sig-events> ]
 :meta/initial-time-sig {:meta/numerator 4 :meta/denominator 4}
 :meta/key-signatures   [ <key-sig-events> ]
 :meta/initial-key      "C major"
 :meta/copyright        "© 2024 Composer Name"
 :meta/text-annotations ["Arranged by..." ...]
 }
```

---

## 4. Namespace & Module Plan

```
midi-analysis/
├── src/
│   └── midi_analysis/
│       ├── core.clj          ; entry point, directory walking
│       ├── parser.clj        ; binary parsing → raw event maps (Pass 1)
│       ├── enricher.clj      ; tempo/time annotation, note pairing (Pass 2)
│       ├── meta.clj          ; meta event decoding & meta-summary assembly
│       ├── notes.clj         ; NoteOn/Off pairing → note objects
│       ├── chords.clj        ; chord snapshot extraction (future)
│       ├── harmony.clj       ; chord labeling, Roman numeral analysis (future)
│       ├── convert.clj       ; Type 1 → Type 0 conversion, Z-prefix writer
│       └── util.clj          ; pitch-name lookup, bpm calc, key-name table
├── test/
│   └── midi_analysis/
│       ├── parser_test.clj
│       ├── meta_test.clj
│       ├── notes_test.clj
│       └── convert_test.clj
└── project.clj / deps.edn
```

**Recommended dependency:** `[com.billosys/clj-midi "0.1.0"]` or direct use of `javax.sound.midi` (standard Java library, no extra deps) for reading raw bytes. For full binary control, direct `java.io.DataInputStream` parsing gives the most flexibility.

---

## 5. Type 1 → Type 0 Conversion Algorithm

Type 0 requires merging all tracks into a single track, re-sorting events by absolute tick, then recomputing delta ticks.

```
1. Parse the Type 1 file into the data structure above.
2. Collect all events from all tracks into one flat sequence.
3. Sort by :event/abs-ticks (stable sort preserves relative order of same-tick events).
4. Recompute :event/delta-ticks for each event:
     delta[0] = abs-ticks[0]
     delta[i] = abs-ticks[i] - abs-ticks[i-1]
5. Retain exactly one :end-of-track meta event, placed last.
6. Serialise back to binary MIDI:
     - Header chunk: type=0, num-tracks=1, ticks-per-beat=<original>
     - Single MTrk chunk with recomputed delta times
7. Write to <original-directory>/Z<original-filename>.
```

**Caveats to handle:**
- Running status (byte-saving encoding) — safest to always write full status bytes in output
- SysEx events spanning multiple chunks — reassemble before merge
- Channel 9 (drums) metadata — preserve program-change events that may be track-local in Type 1

---

## 6. Implementation Phases

### Phase 1 — Parser & Text Meta Events
- Binary parser for header and track chunks
- Delta-time VLQ (variable-length quantity) decoder
- Meta event decoder for all text-class types (0x01–0x07) plus tempo, time-sig, key-sig
- Assemble `:midi/file-map` with `:midi/meta-summary`
- REPL-friendly pretty-print of summary

### Phase 2 — Full Event Parsing & Enrichment
- Channel message parsing (NoteOn, NoteOff, CC, PC, PitchBend)
- Pass 2 enrichment: absolute seconds annotation using tempo map
- Note-on/off pairing → note objects

### Phase 3 — Type 1 → Type 0 Converter
- Merge-and-sort algorithm
- Delta-time recomputation
- Binary serialiser
- Z-prefix file writer with validation (re-parse output and compare event count)

### Phase 4 — Harmonic Analysis (future)
- Chord snapshot extraction from note objects
- Chord recognition (pitch-class set → chord name)
- Key-context Roman numeral labeling
- Progression extraction (sequence of chord labels per measure)

---

## 7. Key Design Decisions & Rationale

| Decision | Rationale |
|---|---|
| Plain maps over records | REPL transparency; maps print, diff, and merge naturally |
| Namespaced keywords | Prevents collisions; enables `clojure.spec` later |
| Store both delta and absolute ticks | Absolute ticks are needed for sorting (Type 0 conversion) and duration math; delta ticks needed for serialisation |
| Separate parse and enrich passes | Keeps parser pure and fast; enrichment (seconds, note pairing) is optional |
| Filtered views in track map | Avoids repeated `filterv` calls in analysis code |
| Derive `:meta/bpm` and `:meta/key-name` at parse time | Human-readable fields cost nothing to store and save every caller from re-computing |
| Chord snapshots as separate step | Chord detection is computationally heavier and not always needed; lazy or on-demand computation fits Clojure idioms |

---

## 8. Open Questions to Resolve

1. **Encoding of text meta events** — MIDI spec says ASCII; real-world files use Latin-1 or UTF-8. Detect or always try UTF-8 with Latin-1 fallback?
2. **Overlapping notes** (same pitch/channel) — stack-based pairing or last-wins?
3. **Type 2 files** — silently skip or report as unsupported?
4. **Large files** — parse eagerly into memory or use lazy sequences? (Lazy is idiomatic Clojure but complicates the two-pass enrichment)
5. **Output validation** — after writing the Z-file, re-parse it and assert event-count equality?
6. **Spec definitions** — add `clojure.spec.alpha` specs for the maps, useful for generative testing of the parser

---

## 9. Deliverables Summary

| Deliverable | Description |
|---|---|
| `parser.clj` | Binary MIDI → Clojure map tree |
| `meta.clj` | Text meta extraction + meta-summary builder |
| `enricher.clj` | Tick-to-seconds pass, note pairing |
| `convert.clj` | Type 1 → Type 0 merger + Z-prefix writer |
| `core.clj` | Directory walker, batch analysis runner |
| `chords.clj` / `harmony.clj` | Stubbed namespaces ready for Phase 4 |
| Test suite | Parser round-trip tests, conversion validation |
| REPL demo | Example session showing map exploration of a real MIDI file |


# Prompt:
- How can MIDI files of Bach chorales be used to test the features of this project?

# Response:

Bach chorales are close to ideal as a test corpus for this project. Here's a thorough breakdown of why, organized by the features being tested:

---

## Why Bach Chorales Are an Excellent Test Corpus

### The Dataset

The standard corpus contains 382 four-part chorales, each representing a sequence of chords over time with four MIDI note values corresponding to soprano, alto, tenor, and bass voices. MIDI files can be sourced from BachCentral.com (used by the UCI dataset), the Boulanger-Lewandowski split widely used in ML research, or Music21's built-in corpus. A Python script exists to turn the JSB Chorales dataset into actual MIDI files at 4th, 8th, or 16th-note quantization levels.

---

### Testing Phase 1: Text Meta Events

Chorale MIDI files from different sources are inconsistent in their metadata, which is actually a strength for testing — you get to exercise many paths through your parser:

- **`:track-name`** — most sequenced versions label each track with the voice name ("Soprano", "Alto", "Tenor", "Bass"), giving you four `:track-name` meta events to extract and roll up into `:meta/meta-summary`
- **`:text` and `:copyright`** — files from BachCentral and other archives often include attribution text annotations, copyright strings, and encoder credits, exercising your text-class meta event decoding
- **`:marker`** — some editions mark phrase boundaries or fermatas, which in chorales are musically significant (fermatas mark cadence points and phrase endings — they're structural markers, not ornamental)
- **`:key-signature`** — chorales are in a wide variety of keys (all major and minor keys appear across the corpus), giving you full coverage of the `:meta/sharps` range from -4 flats to +4 sharps. The UCI dataset notes that the train/test split was made by key, making key-signature extraction directly verifiable
- **`:time-signature`** — the vast majority are in 4/4, but a handful are in 3/4 or 3/8, giving you a simple way to confirm your time-signature decoder handles the denominator's power-of-2 encoding correctly
- **`:set-tempo`** — most chorale MIDI files encode a single tempo, making the tempo map trivial to verify; the BPM should be in a plausible choral range (60–100)

---

### Testing Phase 2: Type 1 → Type 0 Conversion

The four-voice structure of chorales is ideal for conversion testing for a specific reason: **the four tracks are semantically labelled and musically independent**. This lets you verify correctness at the musical level, not just the byte level:

- After merging, you can confirm that the merged track contains exactly `soprano-events + alto-events + tenor-events + bass-events` note events
- You can sort events by absolute tick and verify that no voice's events are interleaved incorrectly — notes that were simultaneous across tracks should still be simultaneous in the merged output (same abs-tick, same beat)
- The **fermata problem** is a good edge case: in Type 1 files, a fermata often extends all four voices simultaneously. After Type 0 conversion, all four NoteOff events should still cluster at the same tick
- You can round-trip test: parse the Type 1 original, convert to Type 0 (Z-prefix), re-parse the Z-file, and assert that the `:midi/meta-summary` is identical (same key, tempo, time signature, track names) and that total note count is preserved

---

### Testing Phase 3 (Future): Harmonic & Chord Analysis

This is where chorales become uniquely powerful as a test corpus:

**Known ground truth exists.** The UCI Bach Choral Harmony dataset contains 60 chorales with 5,665 events, each labelled with one of 101 chord labels, manually annotated by a human expert. This means you can run your chord snapshot extractor against these 60 chorales and compare your output to human-annotated ground truth — a real validation baseline, not just a sanity check.

**Pitch range is bounded and well-understood.** MIDI values across the corpus range from 36 (C2) to 81 (A5). Each voice occupies a predictable range: bass roughly C2–E4, tenor E3–A4, alto G3–D5, soprano C4–A5. Your note-pairing logic can be validated by checking that notes from each track fall within the expected range after the Type 0 merge.

**Voice leading is strict.** Bach's chorales follow well-codified rules (no parallel fifths, leading tone resolutions, etc.), which means:
- Your chord snapshot algorithm can be tested against the expectation that each snapshot should contain exactly 4 pitches (one per voice) except at rests
- Chord progressions should follow expected tonal patterns — I–V–I cadences at fermatas, ii–V–I or IV–V–I approaches, etc. — giving informal but musically meaningful validation of your Roman numeral analysis

**The SATB structure maps directly to your track model.** In a Type 1 chorale file, each track is a single monophonic voice. This is the simplest possible case for note-on/off pairing (no overlapping same-pitch events on the same channel), which makes it the right starting point before tackling more complex polyphonic files.

---

### Practical Testing Strategy

| Test Goal | Chorale Property That Enables It |
|---|---|
| Meta event decoding coverage | Variety of keys, time sigs, and annotation quality across 370+ files |
| Key signature range | Corpus spans roughly all keys from 4 flats to 4 sharps |
| Type 0 merge correctness | 4 tracks → 1; event count exactly verifiable |
| Note-pairing simplicity | Monophonic voices: no same-pitch overlap within a track |
| Chord snapshot validation | Each beat should yield exactly 1 chord of 4 notes |
| Harmonic analysis ground truth | UCI dataset provides human chord labels for 60 chorales |
| Fermata/phrase boundary handling | Markers or extended note durations at cadence points |
| Text encoding robustness | Files from different sources use different Latin-1/UTF-8 conventions |

The one limitation to be aware of: some chorale datasets in their preprocessing lost information present in the original scores — beat positions, key signatures, time signatures, and voice assignments — so the quality of meta events depends heavily on which MIDI source you use. Files from BachCentral or Music21's corpus tend to be the most complete; the Boulanger-Lewandowski pickle format strips much of the metadata entirely and would need to be regenerated as MIDI. Starting with BachCentral files gives you the richest meta event content to parse.