# Rubik's Cube for visionOS — Project Overview

## 1. Concept

A visionOS app that renders a 3D Rubik's Cube in a shared or immersive space, lets the user grab and rotate cube faces with hand gestures (or a fallback gesture/tap interface), and presents the user with a shuffled cube on launch that they attempt to solve.

This document covers:
1. Data structure for cube state
2. Shuffle algorithm
3. Visual enhancement roadmap (materials, shaders, lighting)
4. Xcode project setup
5. Testing on the visionOS simulator

---

## 2. Data Structure for Cube State

### 2.1 The core insight

A 3×3×3 Rubik's Cube has 6 faces, each face has 9 visible stickers, so there are 54 visible colored squares total. The state you need to track is purely **which color sits at each sticker position** — you don't need to model the physical geometry of 26 cubies unless you want physically-accurate animation (see section 2.4).

### 2.2 Recommended representation

**Enum for color:**
Define an enum with six cases — one per face color (e.g., white, yellow, red, orange, blue, green). This gives you type safety and makes invalid states unrepresentable (no "purple" stickers).

**Face identity enum:**
Define an enum for the six face positions in a fixed orientation convention — Up, Down, Front, Back, Left, Right (the standard "URFDLB" or "UDFBLR" naming used in cube-solving literature). Fixing this convention early matters a lot, because your turn algorithm and your renderer both need to agree on which face is which.

**Per-face grid:**
Each face is a 3×3 grid of colors. The natural representation is a fixed-size array of 9 elements (row-major: index 0–2 top row, 3–5 middle row, 6–8 bottom row), rather than a nested array, since a Rubik's face is always exactly 9 stickers — a fixed-size flat array avoids bounds-checking overhead and makes rotation math (see below) a simple index permutation.

**Whole-cube state:**
A dictionary or fixed-size collection keyed by the Face enum, mapping each face to its 9-color array. A dictionary keyed by an enum is convenient for readability; a fixed 6-element array indexed by the enum's raw value is marginally faster and just as clear if you add a small helper for indexing.

### 2.3 Why this representation is convenient

- **Turning a face** becomes two operations: (a) a cyclic permutation of the 9 stickers *within* the turned face itself (corners rotate among themselves, edges rotate among themselves, center stays fixed), and (b) a cyclic permutation of the *outer strips* of the four adjacent faces (three stickers each) that touch the turned face. Both are just index-remapping on fixed-size arrays — no geometry or matrix math needed for the logical state.
- **Solved-state check** is trivial: a face is "solved" if all 9 of its stickers are the same color; the cube is solved if all 6 faces pass that test.
- **Serialization** (for undo/redo, saving progress, or replaying a shuffle) is trivial — the whole state is 54 small enum values, cheaply encodable as a string or array.

### 2.4 Two layers of state (logical vs. visual)

It's worth explicitly separating:
- **Logical state**: the 54-sticker color model above. This is what your solve-checker, shuffle algorithm, and any "hint/solver" feature operate on.
- **Visual/geometric state**: the actual 3D transforms of 26 cubie entities in RealityKit, used only for rendering and animating turns smoothly.

Keeping these separate means your core cube logic is simple, testable, and platform-agnostic (you could unit-test the whole engine without touching RealityKit at all), while the rendering layer is free to animate turns with easing curves, physics, or haptics independent of the underlying model. After each turn's animation completes, you sync the logical state (via the permutation above) and then rebuild or re-color the geometric cubies to match.

---

## 3. Shuffle Algorithm

### 3.1 Goal

Produce a cube state that is (a) always reachable from solved by legal moves — so it's guaranteed solvable — and (b) sufficiently mixed that it doesn't look trivially close to solved.

### 3.2 Approach: random walk of legal turns

The standard, well-tested approach used by virtually every digital cube implementation:

1. Start from the solved state.
2. Define the full move set: each of the 6 faces, each turnable clockwise, counter-clockwise, or 180°— 18 possible discrete moves total (or you can simplify to just clockwise/counter-clockwise and treat 180° as two quarter turns).
3. Pick a target move count — a reasonable threshold is 20–25 random moves, which is roughly the number a competitive human "God's Number" solve needs in the worst case (20 is the proven maximum for an optimal solver; using slightly more compensates for the randomness not being optimal).
4. Repeat for the threshold count:
   - Randomly select one move from the move set.
   - **Avoid the trivial "undo" case**: don't let the newly chosen move be the direct inverse of the immediately preceding move (e.g., don't follow Right-clockwise with Right-counter-clockwise), since that cancels out and effectively wastes a shuffle step.
   - **Avoid redundant same-face repeats**: similarly, don't allow three consecutive turns of the same face, since three of the same quarter-turn is equivalent to one turn the other way, and two is already better expressed as a single half-turn move — both waste entropy.
   - Apply the move to the logical state (the index-permutation described in 2.3).
5. Once the threshold is reached, the resulting state is your shuffled puzzle. Store the move sequence too, if you want an "undo shuffle" or want to verify solvability by simply replaying the exact inverse sequence.

### 3.3 Why not "randomize each sticker directly"?

Randomly assigning colors to all 54 stickers (subject only to "9 of each color") will, with overwhelming probability, produce a state that is **not reachable** by legal turns and therefore mathematically unsolvable. Only roughly 1 in 12 of all naive sticker arrangements corresponds to a legal, solvable cube (because of parity constraints on corner twist, edge flip, and permutation parity). Building the shuffle exclusively out of legal moves sidesteps this entirely — solvability is guaranteed for free.

### 3.4 Presenting the shuffle to the user

You have a UX choice:
- **Instant reveal**: apply all moves to the logical state silently, then render the final shuffled cube directly (fast, feels like "here's your puzzle").
- **Animated shuffle**: play the moves as fast, chained animations on load, so the user sees the cube visibly scrambling (more satisfying, doubles as a nice loading-screen moment, but adds a few seconds before interactivity).

A middle ground many apps use: animate the shuffle at high speed (e.g., 100–150 ms per turn) so it takes only two or three seconds total but still visually reads as "scrambling."

---

## 4. Visual Enhancement Roadmap

Once the core mechanic works with flat-colored materials, there's a lot of room to make the cube feel physically present in the visionOS shared/immersive space:

- **Physically based materials (PBR)**: give the plastic body a matte, slightly rough black or white plastic look, and the stickers a glossy, faintly reflective vinyl look — the contrast between matte body and glossy sticker is a big part of what makes a cube "read" as photoreal rather than flat colored cubes.
- **Custom shaders for sticker edges**: a subtle bevel/rounded-edge shader on each sticker (real cube stickers are slightly domed/rounded) adds a surprising amount of realism versus flat quads.
- **Environment reflections**: leverage visionOS's automatic environment lighting/reflection probes so the glossy stickers and plastic pick up real-world reflections from the user's room, reinforcing the sense that the cube is really sitting on their table.
- **Turn animation easing**: instead of linear rotation, use an ease-in/ease-out curve, plus a small overshoot/settle "snap" when a face lands on a quarter-turn boundary, to sell physicality.
- **Haptic-adjacent audio**: a soft "click" sound synced to each 90° snap goes a long way given visionOS's lack of hand haptics.
- **Ambient occlusion between cubies**: add subtle contact shadows/AO in the seams between cubies so the cube doesn't look like a flat decal-covered block.
- **Depth-of-field / soft shadow grounding**: cast a soft contact shadow onto the real-world surface (via visionOS's shadow/occlusion support) so the cube feels anchored in the room rather than floating.
- **Idle animation**: a very slow ambient rotation or subtle "breathing" scale when untouched, to keep the object feeling alive in a static scene.
- **Solve celebration**: a particle/confetti or glow shader triggered when the solved-state check passes, as a payoff moment.
- **Colorblind-friendly mode**: optionally render small symbols or textures on top of the sticker colors, togglable, so cube colors remain distinguishable for colorblind users.

Most of these — custom bevels, reflections, particle effects — are naturally built with RealityKit's `ShaderGraphMaterial` (visionOS's node-based shader authoring, editable in Reality Composer Pro) rather than hand-written Metal shaders, which keeps them approachable early on while leaving room for hand-written Metal shaders later for effects RealityKit's node graph can't express.

---

## 5. Xcode Project Setup

1. **Create the project**: New Project → visionOS → App. Choose "Mixed" or "Full Space" as the initial immersion style depending on whether you want the cube to sit in the user's room (mixed/shared space) or in a fully custom environment (full space). A cube-solving app is a natural fit for the shared/mixed space, letting the cube sit on the user's real desk.
2. **Framework choices**: SwiftUI for the app's window/UI chrome (menus, shuffle button, timer, move counter), RealityKit for the 3D cube itself, and Reality Composer Pro (bundled with Xcode) for authoring materials/shaders and assembling the cubie models visually rather than purely in code.
3. **Asset organization**: keep a `.reality` or `.usda` scene file (authored in Reality Composer Pro) containing the 26 cubie meshes, referenced into your RealityKit `Entity` hierarchy at runtime; keep sticker materials as swappable `ShaderGraphMaterial` or simple `PhysicallyBasedMaterial` instances so you can recolor them programmatically to match the logical cube state.
4. **Gesture setup**: use SwiftUI's `DragGesture` combined with RealityKit's `RealityView` and spatial tap/drag gesture targeting on entities to detect which face/cubie the user is interacting with, translating drag direction into a face-turn intent.
5. **Target settings**: confirm the deployment target matches the visionOS SDK version you're developing against, and enable hand-tracking or world-sensing capabilities in the target's Info settings only if you go beyond basic RealityView gestures into raw ARKit hand-tracking data.

---

## 6. Testing on the visionOS Simulator

1. **Simulator availability**: install the visionOS platform support via Xcode → Settings → Platforms if it isn't already present; this downloads the visionOS Simulator runtime.
2. **Run destination**: select an "Apple Vision Pro" simulator destination from Xcode's scheme/destination picker, same as choosing an iPhone simulator.
3. **Input simulation**: the simulator doesn't have real hand tracking, but it provides a virtual pointer/gaze-and-pinch simulation you can drive with trackpad/mouse input, plus a keyboard shortcut to simulate a pinch gesture — sufficient for testing tap-to-select and drag-to-turn interactions on cube faces.
4. **Environment simulation**: the simulator lets you place your app content into a few preset simulated rooms so you can sanity-check how the cube's shadows/reflections and shared-space anchoring look against a simulated real-world backdrop.
5. **Immersion style toggling**: you can toggle between windowed, shared space, and full space presentations from within the running simulator session to check your app behaves correctly across all styles if you support more than one.
6. **Performance caveats**: the simulator runs on your Mac's GPU via a compatibility layer, so shader-heavy effects (custom Metal shaders especially) may run slower or look slightly different than on-device. It's normal practice to do final visual/perf validation on a physical Vision Pro when possible, especially before tuning shader complexity for the enhancement items in section 4.
7. **Unit-testing the logical layer separately**: because the cube's logical state (section 2) is decoupled from RealityKit, you can write ordinary Swift unit tests (XCTest) against the move-permutation and shuffle logic without touching the simulator at all — useful for quickly verifying that every move's inverse restores the prior state, and that the shuffle always leaves the cube solvable.

---

## 7. Suggested Next Steps

1. Nail down the logical data model and move-permutation logic first, with unit tests, before touching RealityKit.
2. Build a minimal flat-colored cube in RealityKit driven by that logical state, with simple tap-to-turn interaction (no gestures yet).
3. Layer in drag-based face-turning gestures.
4. Add the shuffle algorithm and a "New Game" flow.
5. Layer in the visual enhancements from section 4 roughly in the order listed — materials and lighting first, particle/celebration effects last.
