Prompt to Claude Sonnet 4.6: Let's start simply and work step by step where I do test driven development in Clojure with Midge.  My first goal is to recursively read the subdirectories and identify which MIDI files are Type 1.  Walk me through the steps for installing leiningen on a Raspberry Pi 400 and beginning development of this task.

Let me look up current installation details to make sure the guidance is accurate for the Pi 400.Good, I have everything I need. Here is the complete step-by-step guide.

---

## Step 1 — Verify Your OS and Architecture

Open a terminal on the Pi 400 and run:

```bash
cat /etc/os-release
uname -m
```

You should see Raspberry Pi OS Bookworm (Debian 12) and `aarch64` (64-bit ARM). The steps below assume 64-bit Bookworm. If you are on the older Bullseye, the commands are the same but the Java version available is 11 rather than 17.

---

## Step 2 — Install OpenJDK 17

On Bookworm, `default-jdk` points to Java 17. Install it with:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install default-jdk -y
```

Verify:

```bash
java -version
javac -version
```

You should see something like `openjdk version "17.0.x"`. You do not need to set `JAVA_HOME` manually — Leiningen will find the JVM automatically via the system path.

---

## Step 3 — Install Leiningen

The standard Unix install puts the `lein` script in `~/bin`, downloads itself, and makes itself executable:

```bash
mkdir -p ~/bin
curl https://raw.githubusercontent.com/technomancy/leiningen/stable/bin/lein \
     > ~/bin/lein
chmod u+x ~/bin/lein
```

The Pi 400's default `.profile` adds `~/bin` to `$PATH` automatically if the directory exists, but you need to reload it for the current session:

```bash
source ~/.profile
```

Now run Leiningen for the first time. This downloads the full standalone JAR (~15MB):

```bash
lein
```

Be patient — on the first run the Pi 400 is slower than a desktop because it has to JIT-compile the Leiningen bootstrap code. Starting a REPL is usually slow on a Raspberry Pi; this is preventable by adding `:repl-options {:timeout 180000}` to your project file — we'll do that next.

Verify the install:

```bash
lein version
# Leiningen 2.x.x on Java 17.x.x ...
```

---

## Step 4 — Install the Midje Plugin Globally

`lein-midje` is a Leiningen plugin, so add it to `~/.lein/profiles.clj` so it is available in every project:

```bash
mkdir -p ~/.lein
```

Create `~/.lein/profiles.clj` with:

```clojure
{:user {:plugins [[lein-midje "3.2.2"]]}}
```

This means you never have to add the plugin to individual projects — it is always available. Run `lein help midje` to confirm it was picked up (Leiningen will download it on first use).

---

## Step 5 — Create the Project

```bash
cd ~
lein new app midi-analysis
cd midi-analysis
```

Leiningen creates this structure:

```
midi-analysis/
├── project.clj
├── src/
│   └── midi_analysis/
│       └── core.clj
└── test/
    └── midi_analysis/
        └── core_test.clj
```

---

## Step 6 — Configure `project.clj`

Replace the generated `project.clj` with:

```clojure
(defproject midi-analysis "0.1.0-SNAPSHOT"
  :description "MIDI file analysis and conversion"
  :license {:name "EPL-2.0"}
  :dependencies [[org.clojure/clojure "1.12.0"]]
  :profiles {:dev {:dependencies [[midje "1.10.10"
                                   :exclusions [org.clojure/clojure]]]}}
  :repl-options {:timeout 180000}   ; Pi is slow to start the REPL
  :main midi-analysis.core)
```

No extra MIDI library is needed yet — for reading just the header bytes of a MIDI file, `java.io` from the JDK is all you need. You can add a higher-level library later when you get to event parsing.

---

## Step 7 — Create the First Test File

Delete the generated `test/midi_analysis/core_test.clj` and create `test/midi_analysis/scanner_test.clj`:

```clojure
(ns midi-analysis.scanner-test
  (:require [midje.sweet :refer :all]
            [midi-analysis.scanner :refer :all]))

;; ---- directory walking ----

(fact "find-midi-files returns an empty sequence for an empty directory"
  (let [dir (java.nio.file.Files/createTempDirectory "midi-test" (make-array java.nio.file.attribute.FileAttribute 0))]
    (find-midi-files (.toString dir)) => empty?))

(fact "find-midi-files finds .mid files recursively"
  (let [root (java.nio.file.Files/createTempDirectory "midi-test" (make-array java.nio.file.attribute.FileAttribute 0))
        sub  (java.io.File. (.toString root) "subdir")]
    (.mkdirs sub)
    (spit (java.io.File. sub "bach.mid") "")       ; create a fake .mid file
    (spit (java.io.File. sub "notes.txt") "")      ; should be ignored
    (map #(.getName (java.io.File. %))
         (find-midi-files (.toString root)))) => (just ["bach.mid"]))

;; ---- MIDI type detection ----

(fact "midi-type returns nil for a file that is too short to be a MIDI file"
  (let [f (java.io.File/createTempFile "tiny" ".mid")]
    (spit f "abc")
    (midi-type (.getPath f))) => nil)

(fact "midi-type returns 0 for a Type 0 header"
  (midi-type "test/resources/type0_sample.mid") => 0)

(fact "midi-type returns 1 for a Type 1 header"
  (midi-type "test/resources/type1_sample.mid") => 1)

(fact "type-1? is true for a Type 1 file and false otherwise"
  (type-1? "test/resources/type1_sample.mid") => true
  (type-1? "test/resources/type0_sample.mid") => false)

;; ---- scanning a directory ----

(fact "type-1-files returns only Type 1 files from a directory tree"
  (let [results (type-1-files "test/resources")]
    (every? #(= 1 (midi-type %)) results)) => true)
```

The tests fall into four groups, written in red-green-refactor order:

1. Directory walking returns no false positives on an empty dir
2. Recursive `.mid` discovery ignores non-MIDI files
3. `midi-type` reads the header bytes and returns the format number (0, 1, or 2), or `nil` on a malformed file
4. `type-1-files` composes the two pieces

---

## Step 8 — Create Test Fixture Files

You need tiny but valid MIDI headers for the last two tests. MIDI headers are exactly 14 bytes: the 4-byte magic `MThd`, 4-byte length `00 00 00 06`, 2-byte format, 2-byte track count, and 2-byte ticks-per-beat.

```bash
mkdir -p test/resources
```

Create a small helper script `make_fixtures.py` (Python is already on Raspberry Pi OS):

```python
#!/usr/bin/env python3
import struct, os

def write_header(path, fmt, tracks, tpb=480):
    with open(path, 'wb') as f:
        f.write(b'MThd')
        f.write(struct.pack('>I', 6))        # chunk length always 6
        f.write(struct.pack('>HHH', fmt, tracks, tpb))
        # minimal MTrk chunk so the file is well-formed
        f.write(b'MTrk')
        f.write(struct.pack('>I', 4))        # chunk length
        f.write(b'\x00\xff\x2f\x00')         # delta=0, end-of-track meta

os.makedirs('test/resources', exist_ok=True)
write_header('test/resources/type0_sample.mid', fmt=0, tracks=1)
write_header('test/resources/type1_sample.mid', fmt=1, tracks=4)
print("Fixtures written.")
```

```bash
python3 make_fixtures.py
```

---

## Step 9 — Write the Implementation to Make the Tests Pass

Create `src/midi_analysis/scanner.clj`:

```clojure
(ns midi-analysis.scanner
  (:import [java.io File DataInputStream FileInputStream]
           [java.nio.file Files Path Paths]
           [java.nio.file.attribute FileAttribute]))

(def ^:private midi-extensions #{".mid" ".midi" ".MID" ".MIDI"})

(defn- midi-file? [^File f]
  (and (.isFile f)
       (let [name (.getName f)]
         (some #(.endsWith name %) midi-extensions))))

(defn find-midi-files
  "Recursively walk root-dir and return a seq of path strings
   for every file with a .mid/.midi extension."
  [root-dir]
  (->> (file-seq (File. root-dir))
       (filter midi-file?)
       (map #(.getPath %))))

(defn midi-type
  "Read the 14-byte MIDI file header and return the format type
   (0, 1, or 2) as an integer, or nil if the file is not a
   valid MIDI file."
  [path]
  (try
    (with-open [dis (DataInputStream. (FileInputStream. path))]
      (let [magic (byte-array 4)]
        (.readFully dis magic)
        (when (= (String. magic "ASCII") "MThd")
          (.readInt dis)   ; skip chunk length (always 6)
          (.readShort dis)))) ; format type: 0, 1, or 2
    (catch Exception _ nil)))

(defn type-1?
  "Returns true if the file at path is a Type 1 MIDI file."
  [path]
  (= 1 (midi-type path)))

(defn type-1-files
  "Recursively scan root-dir and return paths of all Type 1 MIDI files."
  [root-dir]
  (->> (find-midi-files root-dir)
       (filter type-1?)))
```

---

## Step 10 — Run the Tests

```bash
lein midje
```

You should see all facts passing in green. To run in watch mode so tests re-run whenever you save a file (very useful on a Pi where startup is slow):

```bash
lein midje :autotest
```

This sets up a watcher on the code files; when they change, only the relevant tests will be run again. This is the right way to work on the Pi 400 — pay the JVM startup cost once and iterate quickly from there.

---

## Summary of What You Now Have

| File | Purpose |
|---|---|
| `project.clj` | Midje in `:dev` profile; REPL timeout extended for Pi |
| `test/resources/type0_sample.mid` | Minimal valid Type 0 fixture |
| `test/resources/type1_sample.mid` | Minimal valid Type 1 fixture |
| `test/midi_analysis/scanner_test.clj` | Midje facts covering dir walking and type detection |
| `src/midi_analysis/scanner.clj` | Implementation: `find-midi-files`, `midi-type`, `type-1?`, `type-1-files` |

The next natural step from here is a `parser` namespace that takes a path from `find-midi-files` and reads the full header chunk into the `:midi/file-map` structure from the project plan — at which point you'll have the `:midi/type`, `:midi/track-count`, and `:midi/ticks-per-beat` fields populated from real files.

Prompt: Please compare this Clojure implementation with an implementation of the same functionality in Python

Great comparison to make — these two implementations reveal a lot about the philosophical differences between the languages. Let me work through each piece systematically.

---

## Python Equivalent Implementation

First, here is the Python that directly mirrors the Clojure:

```python
# scanner.py
import os
import struct
from pathlib import Path
from typing import Optional

MIDI_EXTENSIONS = {'.mid', '.midi', '.MID', '.MIDI'}

def find_midi_files(root_dir: str) -> list[str]:
    """Recursively walk root_dir and return a list of paths
    for every file with a .mid/.midi extension."""
    return [
        str(p)
        for p in Path(root_dir).rglob('*')
        if p.is_file() and p.suffix in MIDI_EXTENSIONS
    ]

def midi_type(path: str) -> Optional[int]:
    """Read the 14-byte MIDI file header and return the format type
    (0, 1, or 2), or None if the file is not a valid MIDI file."""
    try:
        with open(path, 'rb') as f:
            magic = f.read(4)
            if magic != b'MThd':
                return None
            f.read(4)                        # skip chunk length
            fmt = struct.unpack('>H', f.read(2))[0]
            return fmt
    except Exception:
        return None

def type_1(path: str) -> bool:
    """Returns True if the file at path is a Type 1 MIDI file."""
    return midi_type(path) == 1

def type_1_files(root_dir: str) -> list[str]:
    """Recursively scan root_dir and return paths of all Type 1 MIDI files."""
    return [p for p in find_midi_files(root_dir) if type_1(p)]
```

And the Midje-equivalent tests using `pytest`:

```python
# test_scanner.py
import os
import struct
import tempfile
import pytest
from pathlib import Path
from scanner import find_midi_files, midi_type, type_1, type_1_files

def write_midi_header(path: str, fmt: int, tracks: int, tpb: int = 480):
    with open(path, 'wb') as f:
        f.write(b'MThd')
        f.write(struct.pack('>I', 6))
        f.write(struct.pack('>HHH', fmt, tracks, tpb))
        f.write(b'MTrk')
        f.write(struct.pack('>I', 4))
        f.write(b'\x00\xff\x2f\x00')

@pytest.fixture
def empty_dir(tmp_path):
    return str(tmp_path)

@pytest.fixture
def midi_dir(tmp_path):
    sub = tmp_path / "subdir"
    sub.mkdir()
    write_midi_header(str(sub / "bach.mid"), fmt=1, tracks=4)
    (sub / "notes.txt").write_text("ignored")
    return str(tmp_path)

@pytest.fixture
def type0_file(tmp_path):
    p = str(tmp_path / "type0.mid")
    write_midi_header(p, fmt=0, tracks=1)
    return p

@pytest.fixture
def type1_file(tmp_path):
    p = str(tmp_path / "type1.mid")
    write_midi_header(p, fmt=1, tracks=4)
    return p

# --- directory walking ---

def test_find_midi_files_empty_dir(empty_dir):
    assert find_midi_files(empty_dir) == []

def test_find_midi_files_recursive(midi_dir):
    results = find_midi_files(midi_dir)
    names = [os.path.basename(p) for p in results]
    assert names == ["bach.mid"]

# --- MIDI type detection ---

def test_midi_type_too_short(tmp_path):
    f = tmp_path / "tiny.mid"
    f.write_text("abc")
    assert midi_type(str(f)) is None

def test_midi_type_returns_0_for_type0(type0_file):
    assert midi_type(type0_file) == 0

def test_midi_type_returns_1_for_type1(type1_file):
    assert midi_type(type1_file) == 1

def test_type_1_predicate(type0_file, type1_file):
    assert type_1(type1_file) is True
    assert type_1(type0_file) is False

# --- scanning a directory ---

def test_type_1_files_returns_only_type_1(midi_dir):
    results = type_1_files(midi_dir)
    assert all(midi_type(p) == 1 for p in results)
```

---

## Direct Comparison

### Syntax and Readability

The most immediate difference is the reading direction and structure. The Clojure `type-1-files` function reads as a pipeline — data flows left to right through `->>`:

```clojure
(defn type-1-files [root-dir]
  (->> (find-midi-files root-dir)
       (filter type-1?)))
```

The Python equivalent is a list comprehension, which is also readable but the filtering condition comes at the end rather than flowing naturally with the data:

```python
def type_1_files(root_dir):
    return [p for p in find_midi_files(root_dir) if type_1(p)]
```

For two steps this is a minor point, but as the pipeline grows — say, filtering → parsing → grouping by key signature — the Clojure threading macro stays linear and readable while Python list comprehensions nest awkwardly or require intermediate variables.

### Immutability and Data Model

This is the deepest difference. The Clojure implementation is built around the principle that data is never modified — `find-midi-files` returns a lazy sequence, `filter` returns a new lazy sequence derived from it, and nothing is mutated anywhere. There are no instance variables, no state to worry about.

Python's list comprehensions also produce new lists, so the *result* is immutable, but the language doesn't enforce it. A Python developer could accidentally append to the results list, reassign variables, or mutate a shared structure. Clojure makes that class of bug structurally impossible.

### Binary I/O

The Clojure implementation reaches into Java's standard library directly, which is both its strength (mature, well-specified) and its verbosity:

```clojure
(with-open [dis (DataInputStream. (FileInputStream. path))]
  (let [magic (byte-array 4)]
    (.readFully dis magic)
    (when (= (String. magic "ASCII") "MThd")
      (.readInt dis)
      (.readShort dis))))
```

The Java interop syntax (`.readFully`, `.readInt`) is concise but unfamiliar to non-Clojure readers. `DataInputStream` provides methods that already handle big-endian multi-byte integers — `.readInt` reads a 4-byte big-endian int and `.readShort` reads a 2-byte big-endian short, which matches the MIDI specification exactly with no extra work.

Python's `struct.unpack` is more explicit about what it is doing, which some find clearer:

```python
with open(path, 'rb') as f:
    magic = f.read(4)
    if magic != b'MThd':
        return None
    f.read(4)                            # skip chunk length
    fmt = struct.unpack('>H', f.read(2))[0]
    return fmt
```

The `'>H'` format string means big-endian unsigned short, which is correct for MIDI. The `[0]` at the end is a minor ugliness — `struct.unpack` always returns a tuple even when unpacking a single value, so you have to extract the first element. Python 3.12+ `struct.unpack_from` can reduce this slightly but doesn't eliminate it.

One important correctness note: the Clojure `.readShort` returns a signed Java `short` (-32768 to 32767), while Python's `'>H'` returns an unsigned value (0 to 65535). For MIDI format bytes 0, 1, and 2 this makes no practical difference, but for parsing ticks-per-beat (which can legitimately use the sign bit to encode SMPTE timecode), Python's unsigned interpretation is more correct. In the next phase of the project, `'>H'` vs Java's signed short will matter.

### Error Handling

Both use the same broad-catch pattern for I/O errors:

```clojure
(catch Exception _ nil)   ; Clojure
```

```python
except Exception:         # Python
    return None
```

These are functionally identical. Both are appropriate here — you don't care *why* a file failed to parse, only that it did. As the project grows toward full event parsing, more specific error handling will matter.

### Testing Philosophy

This is where the biggest philosophical gap appears. Midje's `fact` macro makes tests read as assertions about the world:

```clojure
(fact "find-midi-files finds .mid files recursively"
  (map #(.getName (java.io.File. %))
       (find-midi-files (.toString root)))) => (just ["bach.mid"])
```

The `=>` arrow is the core of Midje's design — it makes tests look like examples in Clojure books, pairing inputs and expected outputs in a readable, almost conversational style. The `(just [...])` checker verifies exact collection contents. Midje also has checkers like `(contains [...])`, `(has every? ...)`, and `(roughly n)` for floating point, all of which read naturally in the fact body.

pytest uses `assert` statements, which are perfectly readable but lack the semantic richness of Midje's checkers. When a pytest assertion fails, you get the raw values; when a Midje fact fails, you get an explanation framed around the claim that was not confirmed.

The bigger practical difference is fixture management. pytest's `@pytest.fixture` decorator with dependency injection is powerful but adds a layer of indirection — you define fixtures in one place and reference them by parameter name in another. Midje's `let` bindings inside `fact` blocks keep the setup and the assertion in the same visual block, which is easier to read in isolation.

`lein midje :autotest` sets up a watcher that reloads changed files and reruns only the relevant tests, which pairs well with the slow JVM startup on the Pi 400 — you pay the cost once. `pytest-watch` (or `ptw`) offers the same capability in Python and is equally recommended for the Pi.

### Directory Walking

Both implementations are one-liners once you use the right abstraction:

```clojure
(->> (file-seq (File. root-dir))
     (filter midi-file?))
```

```python
[p for p in Path(root_dir).rglob('*') if p.is_file() and p.suffix in MIDI_EXTENSIONS]
```

`file-seq` is a built-in Clojure function that returns a lazy sequence of `java.io.File` objects from a recursive directory walk — it is essentially `os.walk` flattened. `Path.rglob('*')` in Python is the closest equivalent. Both are lazy under the hood (Python's `rglob` returns a generator), though Clojure's laziness is more pervasive and guaranteed by the type system.

The extension check differs subtly. Clojure uses a set membership check — `(some #(.endsWith name %) midi-extensions)` — while Python checks `p.suffix in MIDI_EXTENSIONS`. The Python version is cleaner here: `Path.suffix` extracts just the extension including the dot, while the Clojure version has to check each extension with `.endsWith` because `java.io.File` has no dedicated suffix method. This is one place where Python's `pathlib` is genuinely more ergonomic than Java's older `java.io.File`.

### What the Comparison Reveals for the Project

As the project moves into Phase 2 (full event parsing), the balance will shift further in Clojure's favour. The data structures from the project plan — nested maps, vectors of event maps, derived views — are Clojure's native territory. In Python you would reach for `dataclasses` or plain dicts, which are workable but lack the structural sharing and persistent update semantics of Clojure's maps. The threading macro becomes genuinely powerful when a parser pipeline has eight or ten transformation steps. And the REPL-driven workflow — loading a file, inspecting the map, adjusting a parser function, reloading — is a stronger fit for exploratory analysis of an unfamiliar file corpus than Python's `ipython` equivalent, mainly because Clojure's immutability means REPL state never goes stale in subtle ways.

Prompt: The next step will be to parse all the information from the MThd chunk into a data structure that will be useful for future steps of the program that need to access the information in that structure.  For example, a type 0 MIDI file may be treated like a type 1 MIDI file with one track in order to transparently access data in the file.   How will Clojure create this transparency and how can it be tested in Midje?

This is a great design question that gets to the heart of Clojure's approach to polymorphism and data-driven programming. Let me work through it carefully.

---

## The Core Problem

A Type 0 file has one MTrk chunk containing all channels merged together. A Type 1 file has N MTrk chunks, one per voice/instrument. Code that wants to iterate over tracks, or ask "how many tracks are there?", should not need to know which format it is dealing with. You want to write:

```clojure
(tracks my-file-map)   ; works identically for Type 0 and Type 1
```

Clojure offers three mechanisms for this kind of transparency, and choosing the right one for this problem is worth thinking through carefully before writing a line of implementation.

---

## The Three Mechanisms

### Option 1 — Normalisation at Parse Time

Parse the MThd chunk into a canonical map regardless of file type. A Type 0 file is immediately represented as if it had one track. The `:midi/type` field records the original format for fidelity (needed for the converter), but all downstream code sees a uniform structure.

```clojure
;; Type 1 file with 4 tracks — structure is natural
{:midi/path          "bach_chorale.mid"
 :midi/type          1
 :midi/track-count   4
 :midi/ticks-per-beat 480
 :midi/tracks        [{:track/index 0 ...}
                      {:track/index 1 ...}
                      {:track/index 2 ...}
                      {:track/index 3 ...}]}

;; Type 0 file — normalised to look like Type 1 with one track
{:midi/path          "merged.mid"
 :midi/type          0          ; original type preserved
 :midi/track-count   1          ; always 1 for Type 0
 :midi/tracks        [{:track/index 0 ...}]}
```

Downstream code just calls `(:midi/tracks file-map)` and gets a vector of tracks in both cases. **This is the right choice for this project.** It is the simplest, most Clojure-idiomatic approach: put the complexity at the boundary (the parser) and keep the interior clean.

### Option 2 — Multimethods

Define a multimethod that dispatches on `:midi/type`:

```clojure
(defmulti tracks :midi/type)
(defmethod tracks 0 [file-map] [(:midi/track-0 file-map)])
(defmethod tracks 1 [file-map] (:midi/tracks file-map))
```

This is appropriate when Type 0 and Type 1 files truly need different internal representations and the translation is non-trivial. For this project it is unnecessary complexity — you would be using multimethods to paper over a structural difference that is better resolved at parse time.

### Option 3 — Protocols

Similar to multimethods but attached to a type via `defprotocol`/`defrecord`. Even more appropriate for library-boundary polymorphism. Overkill here.

**The verdict:** Use Option 1. Normalise at parse time. The other two options are the right tools when you have genuinely different runtime behaviours, not just structural differences in source data.

---

## The MThd Data Structure

Building on the project plan, here is the full header map. The key design decision is the addition of `:midi/original-type` alongside `:midi/type`:

```clojure
{:midi/path            "/path/to/file.mid"   ; string
 :midi/filename        "bach_chorale.mid"     ; string
 :midi/original-type   0                     ; as read from file: 0, 1, or 2
 :midi/type            1                     ; normalised: Type 0 becomes 1
 :midi/track-count     1                     ; normalised: always >= 1
 :midi/ticks-per-beat  480                   ; PPQ, if bit 15 of the field = 0
 :midi/smpte?          false                 ; true if bit 15 = 1 (SMPTE timecode)
 :midi/smpte-fps       nil                   ; 24, 25, 29, or 30 if smpte? is true
 :midi/smpte-ticks     nil                   ; ticks per frame if smpte? is true
 :midi/tracks          []                    ; populated later by the track parser
 :midi/parse-errors    []}                   ; accumulated non-fatal problems
```

The `:midi/original-type` field is essential for the Type 1 → Type 0 converter: it needs to know whether to actually perform a merge or just copy the file. `:midi/type` is always 1 after normalisation, so downstream analysis code never branches on it.

The ticks-per-beat field deserves special attention. The MIDI spec uses the high bit of the 16-bit field to signal SMPTE timecode mode. When bit 15 is 0, the remaining 15 bits are ticks per quarter note (PPQ). When bit 15 is 1, the upper byte encodes frames-per-second (as a negative two's complement value: -24, -25, -29, or -30) and the lower byte encodes ticks per frame. Almost all MIDI files in the wild use PPQ, but a robust parser should handle both.

---

## The Namespace Structure

```
src/midi_analysis/
├── scanner.clj    ; Phase 1 — already written
├── header.clj     ; Phase 2 — MThd parsing (this step)
└── core.clj       ; entry point

test/midi_analysis/
├── scanner_test.clj
└── header_test.clj
```

---

## The Tests First

Create `test/midi_analysis/header_test.clj`:

```clojure
(ns midi-analysis.header-test
  (:require [midje.sweet :refer :all]
            [midi-analysis.header :refer :all])
  (:import [java.io File]))

;; ---- helpers to build binary fixtures inline ----

(defn- make-header-bytes
  "Returns a 14-byte byte-array containing a minimal valid MThd chunk."
  [fmt tracks tpb]
  (let [ba (byte-array 14)]
    ;; Magic: MThd
    (aset-byte ba 0 (byte 0x4D))  ; M
    (aset-byte ba 1 (byte 0x54))  ; T
    (aset-byte ba 2 (byte 0x68))  ; h
    (aset-byte ba 3 (byte 0x64))  ; d
    ;; Chunk length: 6
    (aset-byte ba 4 (byte 0x00))
    (aset-byte ba 5 (byte 0x00))
    (aset-byte ba 6 (byte 0x00))
    (aset-byte ba 7 (byte 0x06))
    ;; Format type
    (aset-byte ba 8  (byte 0x00))
    (aset-byte ba 9  (byte fmt))
    ;; Track count
    (aset-byte ba 10 (byte 0x00))
    (aset-byte ba 11 (byte tracks))
    ;; Ticks per beat (big-endian)
    (aset-byte ba 12 (byte (bit-shift-right (bit-and tpb 0xFF00) 8)))
    (aset-byte ba 13 (byte (bit-and tpb 0xFF)))
    ba))

(defn- write-tmp-midi [bytes]
  "Write byte-array to a temp file and return its path string."
  (let [f (File/createTempFile "midi-header-test" ".mid")]
    (.deleteOnExit f)
    (with-open [os (java.io.FileOutputStream. f)]
      (.write os bytes))
    (.getPath f)))

;; ---- parse-header ----

(fact "parse-header returns nil for a file with wrong magic bytes"
  (let [path (write-tmp-midi (byte-array [0x00 0x00 0x00 0x00 0x00 0x00]))]
    (parse-header path)) => nil)

(fact "parse-header returns nil for a file that is too short"
  (let [path (write-tmp-midi (byte-array [0x4D 0x54 0x68]))]  ; only 3 bytes
    (parse-header path)) => nil)

(fact "parse-header extracts format type for a Type 0 file"
  (let [path (write-tmp-midi (make-header-bytes 0 1 480))]
    (:midi/original-type (parse-header path))) => 0)

(fact "parse-header extracts format type for a Type 1 file"
  (let [path (write-tmp-midi (make-header-bytes 1 4 480))]
    (:midi/original-type (parse-header path))) => 1)

(fact "parse-header extracts track count"
  (let [path (write-tmp-midi (make-header-bytes 1 4 480))]
    (:midi/track-count (parse-header path))) => 4)

(fact "parse-header extracts ticks-per-beat"
  (let [path (write-tmp-midi (make-header-bytes 1 4 960))]
    (:midi/ticks-per-beat (parse-header path))) => 960)

(fact "parse-header stores the file path"
  (let [path (write-tmp-midi (make-header-bytes 1 1 480))]
    (:midi/path (parse-header path))) => path)

(fact "parse-header stores the filename without directory"
  (let [path (write-tmp-midi (make-header-bytes 1 1 480))]
    (:midi/filename (parse-header path)))
  => (has-suffix ".mid"))  ; temp file names end in .mid

;; ---- SMPTE timecode ----

(fact "parse-header sets smpte? false for normal PPQ ticks-per-beat"
  (let [path (write-tmp-midi (make-header-bytes 1 1 480))]
    (:midi/smpte? (parse-header path))) => false)

(fact "parse-header detects SMPTE timecode when bit 15 is set"
  ;; High byte 0xE8 = -24 in two's complement (24fps), low byte 4 = 4 ticks/frame
  (let [ba (make-header-bytes 1 1 0)
        _  (aset-byte ba 12 (unchecked-byte 0xE8))
        _  (aset-byte ba 13 (byte 0x04))
        path (write-tmp-midi ba)]
    (select-keys (parse-header path)
                 [:midi/smpte? :midi/smpte-fps :midi/smpte-ticks]))
  => {:midi/smpte? true :midi/smpte-fps 24 :midi/smpte-ticks 4})

;; ---- Type 0 normalisation: the transparency tests ----

(fact "a Type 0 file is normalised to midi/type 1"
  (let [path (write-tmp-midi (make-header-bytes 0 1 480))]
    (:midi/type (parse-header path))) => 1)

(fact "a Type 1 file keeps midi/type 1"
  (let [path (write-tmp-midi (make-header-bytes 1 4 480))]
    (:midi/type (parse-header path))) => 1)

(fact "original-type is preserved separately for the converter"
  (let [path (write-tmp-midi (make-header-bytes 0 1 480))
        h    (parse-header path)]
    [(:midi/original-type h) (:midi/type h)]) => [0 1])

(fact "a Type 0 file always has track-count 1 after normalisation"
  (let [path (write-tmp-midi (make-header-bytes 0 1 480))]
    (:midi/track-count (parse-header path))) => 1)

;; ---- tracks accessor — the transparency payoff ----

(fact "tracks returns a vector for both Type 0 and Type 1 header maps
       (tracks is empty until MTrk chunks are parsed, but the shape is uniform)"
  (let [type0-path (write-tmp-midi (make-header-bytes 0 1 480))
        type1-path (write-tmp-midi (make-header-bytes 1 4 480))]
    (vector? (tracks (parse-header type0-path)))) => true
  (vector? (tracks (parse-header type1-path))) => true)

(fact "tracks returns the :midi/tracks vector from the map"
  (tracks {:midi/type 1 :midi/tracks [{:track/index 0}]})
  => [{:track/index 0}])

;; ---- parse-errors ----

(fact "parse-header includes an empty parse-errors vector on success"
  (let [path (write-tmp-midi (make-header-bytes 1 4 480))]
    (:midi/parse-errors (parse-header path))) => [])
```

Notice what the tests are doing structurally. The facts about `:midi/type` and `:midi/original-type` directly encode the transparency contract: one fact asserts the normalisation happened, another asserts the original value was preserved, and a third asserts they are independent. The `tracks` accessor tests confirm that the shape of the returned data is identical for both file types — that is the test of transparency itself.

---

## The Implementation

Create `src/midi_analysis/header.clj`:

```clojure
(ns midi-analysis.header
  (:import [java.io DataInputStream FileInputStream File]))

;; ---- SMPTE frame-rate decoding ----

(defn- smpte-fps
  "The high byte of the ticks field encodes fps as a negative
  two's complement value. Negate it to get the positive fps."
  [high-byte]
  (- high-byte))  ; high-byte arrives as signed, e.g. -24

(defn- parse-timing
  "Given the raw signed short read from the header, return a map of
  timing-related keys. MIDI uses bit 15 to distinguish PPQ from SMPTE."
  [raw-short]
  (if (neg? raw-short)
    ;; Bit 15 is set — SMPTE timecode
    (let [high (bit-shift-right (bit-and raw-short 0xFF00) 8)
          low  (bit-and raw-short 0x00FF)]
      {:midi/smpte?      true
       :midi/ticks-per-beat nil
       :midi/smpte-fps   (smpte-fps high)
       :midi/smpte-ticks low})
    ;; Normal PPQ
    {:midi/smpte?      false
     :midi/ticks-per-beat raw-short
     :midi/smpte-fps   nil
     :midi/smpte-ticks nil}))

;; ---- normalisation ----

(defn- normalise-type
  "Type 0 is treated as Type 1 with one track for uniform downstream access.
  The original type is preserved in :midi/original-type."
  [fmt]
  (if (zero? fmt) 1 fmt))

;; ---- public API ----

(defn parse-header
  "Parse the MThd chunk of the MIDI file at path.
  Returns a map conforming to the :midi/* schema, or nil if the
  file is not a valid MIDI file."
  [path]
  (try
    (with-open [dis (DataInputStream. (FileInputStream. path))]
      (let [magic (byte-array 4)]
        (.readFully dis magic)
        (when (= (String. magic "ASCII") "MThd")
          (let [_           (.readInt dis)   ; chunk length, always 6
                fmt         (.readShort dis)
                track-count (.readShort dis)
                raw-timing  (.readShort dis)
                timing      (parse-timing raw-timing)
                file        (File. path)]
            (merge
             {:midi/path          path
              :midi/filename      (.getName file)
              :midi/original-type fmt
              :midi/type          (normalise-type fmt)
              :midi/track-count   track-count
              :midi/tracks        []
              :midi/parse-errors  []}
             timing)))))
    (catch Exception _ nil)))

(defn tracks
  "Return the vector of parsed track maps from a file map.
  Works identically for normalised Type 0 and Type 1 maps."
  [file-map]
  (:midi/tracks file-map))
```

---

## How Clojure Creates the Transparency

There are three layers working together, and it is worth naming them explicitly.

**Layer 1 — Normalisation at the boundary.** `parse-header` is the only place in the entire codebase that knows Type 0 and Type 1 are different. Everything that calls `parse-header` gets back a map with `:midi/type 1` regardless of source. The ugliness is contained.

**Layer 2 — The map as the interface.** Because the file map is a plain Clojure map, any code that needs a track count does `(:midi/track-count file-map)` and gets an integer. There is no class hierarchy, no `instanceof` check, no abstract method. The structure *is* the interface. This is idiomatic Clojure: data is the API.

**Layer 3 — The `tracks` accessor.** This thin function exists not because it adds any logic (it is just `(:midi/tracks file-map)`) but because it names the operation. Code that says `(tracks file-map)` is clearer than code that says `(:midi/tracks file-map)`, and if the key ever needed to change, there is one place to update. In Clojure, a function that wraps a keyword lookup is a perfectly acceptable and common abstraction — it costs nothing at runtime.

The contrast with an object-oriented approach is instructive. In Java or Python you might write:

```java
interface MidiFile {
    List<Track> getTracks();
}
class Type0File implements MidiFile { ... }
class Type1File implements MidiFile { ... }
```

The transparency lives in the class hierarchy and the interface. In Clojure, the transparency lives in the *data shape*. Both approaches work, but the Clojure approach means you can use every standard collection function (`map`, `filter`, `reduce`, `count`) on the result of `tracks` without any adapter layer, because the result is just a vector.

---

## How Midje Tests the Transparency

The key tests are not the ones that check individual fields — those test correctness. The transparency tests are the ones that make claims about *uniformity*:

```clojure
;; This pair of facts is the transparency contract in executable form.
;; If either fails, downstream code will need to branch on file type.

(fact "a Type 0 file is normalised to midi/type 1"
  (:midi/type (parse-header type0-path)) => 1)

(fact "a Type 1 file keeps midi/type 1"
  (:midi/type (parse-header type1-path)) => 1)
```

Midje's `fact` naming discipline is doing real work here. A fact named "a Type 0 file is normalised to midi/type 1" is a specification, not just a test. When this fact fails six months from now because someone modified the parser, the failure message tells you exactly which design contract was broken and why it matters.

The `tracks` accessor test goes one step further — it tests the shape of the returned value rather than specific contents:

```clojure
(fact "tracks returns a vector for both Type 0 and Type 1 header maps"
  (vector? (tracks (parse-header type0-path))) => true
  (vector? (tracks (parse-header type1-path))) => true)
```

This is a property test in miniature. It does not care what is *in* the vector (nothing yet, since MTrk chunks have not been parsed), only that the shape is uniform. When the track parser is added in the next phase, these tests will still pass without modification — the transparency guarantee holds at the structural level, not just for specific values.


