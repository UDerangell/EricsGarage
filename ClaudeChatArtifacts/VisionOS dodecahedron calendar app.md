# VisionOS dodecahedron calendar app

**Exported with:** [AI Chat Exporter](https://ai-chat-exporter.covai.org)  
**Source:** Claude  
**Date:** 8/13/2026, 2:07:33 PM  
**Link:** [https://claude.ai/chat/0475f2f6-a420-45c5-bfd1-c851220088c0](https://claude.ai/chat/0475f2f6-a420-45c5-bfd1-c851220088c0)  
**Model:** claude-sonnet-5  

## Prompt:
Please create a VisionOS app that shows a dodecahedron with one pentagonal face directly in front of the user.  Add the abbreviation for the current month, and current year,  as text on that face.  Add the abbreviations for the 5 previous months and year  as text on the other visible pentagonal faces.  For the non-visible faces, add the abbreviations for the remaining 6 months plus year of the previous year.  Discuss any text rendering and user interface for future versions of this application where the user will want to select one of the months and have the app respond somehow using data from that month.

## Response:
Now let me verify the RealityKit APIs I'll use are current, then build the project files.

Now the app entry point and views:

This looks solid. Now let me write the README with setup instructions and the requested design discussion.

Let me do a final check of the whole tree and package it up.

I built a visionOS app with 6 Swift files (plus a README). A quick summary of how it's structured:

**Geometry** — I didn't hand-type the dodecahedron's vertex/face data; I generated and verified it with NumPy/SciPy (convex hull, then checked every vertex touches exactly 3 faces, every edge is shared by exactly 2 faces, and Euler's formula holds) so it's a genuine regular dodecahedron, then rotated it so face 0's normal points at the user.

**Face layout** (today, Jul 31 2026):
- Front face: **Jul 2026**
- 5 visible ring faces: Jun, May, Apr, Mar, Feb 2026
- 6 hidden faces: the remaining months (Jan, Aug, Sep, Oct, Nov, Dec), all labeled **2025** per your spec

This is computed at runtime from the actual date (`MonthFaceLabeler.swift`), not hardcoded — the previous-5-months correctly roll across a year boundary if you run it in, say, February.

**Text on pentagons** — RealityKit has no native "text on an arbitrary mesh" primitive, so each face's month/year is rasterized to a small texture and UV-mapped onto that face's own pentagon geometry (computed from its actual vertices, not guessed).

**Note on buildability**: this sandbox has no Xcode/visionOS toolchain, so I couldn't compile or run this — it's plain Swift files meant to be dropped into a new Xcode visionOS App project (instructions are in the README).

The README also contains the discussion you asked for on text rendering trade-offs and how I'd evolve this toward tap-to-select-a-month, including why I already gave every face a `MonthFaceComponent` + tap handler as a hook for that.

## Response:
> **Artifact: gen_dodeca**
```python
import numpy as np

phi = (1 + 5**0.5) / 2

# 20 vertices of a regular dodecahedron
verts = []
for sx in (1,-1):
    for sy in (1,-1):
        for sz in (1,-1):
            verts.append((sx*1, sy*1, sz*1))
for sy in (1,-1):
    for sz in (1,-1):
        verts.append((0, sy*(1/phi), sz*phi))
for sx in (1,-1):
    for sz in (1,-1):
        verts.append((sx*(1/phi), sz*phi, 0))
for sx in (1,-1):
    for sy in (1,-1):
        verts.append((sx*phi, 0, sy*(1/phi)))

verts = np.array(verts, dtype=float)
print("num verts", len(verts))

# 12 face normal directions (icosahedron vertex directions)
normals = []
for sy in (1,-1):
    for sz in (1,-1):
        normals.append((0, sy*1, sz*phi))
for sx in (1,-1):
    for sy in (1,-1):
        normals.append((sx*1, sy*phi, 0))
for sx in (1,-1):
    for sz in (1,-1):
        normals.append((sx*phi, 0, sz*1))
normals = np.array(normals, dtype=float)
normals = normals / np.linalg.norm(normals, axis=1, keepdims=True)
print("num normals", len(normals))

faces = []
for n in normals:
    dots = verts @ n
    idx = np.argsort(-dots)[:5]
    pts = verts[idx]
    centroid = pts.mean(axis=0)
    arb = np.array([1.0,0.0,0.0])
    if abs(np.dot(arb, n)) > 0.9:
        arb = np.array([0.0,1.0,0.0])
    u = np.cross(n, arb)
    u = u/np.linalg.norm(u)
    v = np.cross(n, u)
    angles = []
    for p in pts:
        d = p - centroid
        au = np.dot(d,u)
        av = np.dot(d,v)
        angles.append(np.arctan2(av, au))
    order = np.argsort(angles)
    ordered_idx = [idx[o] for o in order]
    faces.append(ordered_idx)

faces = np.array(faces)
print("faces shape", faces.shape)

for fi in range(len(faces)):
    face = faces[fi]
    pts = verts[face]
    a,b,c = pts[0], pts[1], pts[2]
    n_calc = np.cross(b-a, c-a)
    n_calc = n_calc/np.linalg.norm(n_calc)
    dot = np.dot(n_calc, normals[fi])
    if dot < 0:
        faces[fi] = face[::-1]

print("VERTS")
for v in verts:
    print(list(v))
print("FACES")
for f in faces:
    print(list(f))
print("NORMALS")
for n in normals:
    print(list(n))

np.save('verts.npy', verts)
np.save('faces.npy', faces)
np.save('normals.npy', normals)
```

## Response:
> **Artifact: DodecahedronGeometry**
```plaintext
import Foundation
import RealityKit
import simd
#if canImport(UIKit)
import UIKit
#endif

/// Geometric data for a regular dodecahedron, pre-computed and verified offline
/// (20 unique vertices shared by 3 faces each, 30 unique edges each shared by
/// exactly 2 faces, 12 pentagonal faces — Euler check V-E+F = 20-30+12 = 2).
///
/// The whole solid has already been rotated so that **face 0's** outward
/// normal points down +Z. In RealityKit's world/scene space, +Z points back
/// toward the viewer, so face 0 is the face that faces the user head-on.
enum DodecahedronGeometry {

    /// The 20 vertex positions (unscaled, circumradius = sqrt(3)).
    static let vertices: [SIMD3<Float>] = [
        SIMD3<Float>(-0.324992, 1.000000, -1.376365),
        SIMD3<Float>(-1.376365, 1.000000, 0.324992),
        SIMD3<Float>(-0.324992, -1.000000, -1.376365),
        SIMD3<Float>(-1.376365, -1.000000, 0.324992),
        SIMD3<Float>(1.376365, 1.000000, -0.324992),
        SIMD3<Float>(0.324992, 1.000000, 1.376365),
        SIMD3<Float>(1.376365, -1.000000, -0.324992),
        SIMD3<Float>(0.324992, -1.000000, 1.376365),
        SIMD3<Float>(0.850579, 0.618034, -1.376426),
        SIMD3<Float>(-0.850579, 0.618034, 1.376426),
        SIMD3<Float>(0.850579, -0.618034, -1.376426),
        SIMD3<Float>(-0.850579, -0.618034, 1.376426),
        SIMD3<Float>(-0.525748, 1.618034, -0.324892),
        SIMD3<Float>(-0.525748, -1.618034, -0.324892),
        SIMD3<Float>(0.525748, 1.618034, 0.324892),
        SIMD3<Float>(0.525748, -1.618034, 0.324892),
        SIMD3<Float>(-1.051534, 0.000000, -1.376327),
        SIMD3<Float>(-1.701319, 0.000000, -0.324831),
        SIMD3<Float>(1.701319, 0.000000, 0.324831),
        SIMD3<Float>(1.051534, 0.000000, 1.376327),
    ]

    /// The 12 pentagonal faces, each a list of 5 vertex indices, wound
    /// counter-clockwise as seen from *outside* the solid (i.e. consistent
    /// with each face's outward-pointing normal).
    static let faces: [[Int]] = [
        [9, 11, 7, 19, 5],   // 0  <-- front face (faces the user, +Z)
        [12, 1, 9, 5, 14],   // 1
        [4, 14, 5, 19, 18],  // 2
        [10, 8, 4, 18, 6],   // 3
        [13, 2, 10, 6, 15],  // 4
        [7, 15, 6, 18, 19],  // 5
        [17, 16, 2, 13, 3],  // 6
        [1, 17, 3, 11, 9],   // 7
        [3, 13, 15, 7, 11],  // 8
        [16, 17, 1, 12, 0],  // 9
        [2, 16, 0, 8, 10],   // 10 <-- back face (opposite the user, -Z)
        [0, 12, 14, 4, 8],   // 11
    ]

    /// Index of the face pointing straight at the user.
    static let frontFaceIndex = 0

    /// Index of the face pointing straight away from the user.
    static let backFaceIndex = 10

    /// The 5 faces sharing an edge with the front face, ordered going
    /// around the front face (used to lay out the 5 "previous month" faces).
    static let frontRing: [Int] = [5, 2, 1, 7, 8]

    /// The 5 faces sharing an edge with the back face, ordered to continue
    /// the same rotational direction as `frontRing` (used to lay out the
    /// remaining 5 "previous year" faces once the back face itself, index
    /// `backFaceIndex`, has taken the 6th "remaining" month).
    static let backRing: [Int] = [6, 9, 11, 3, 4]

    /// Uniform scale applied to `vertices` so the solid is a comfortable
    /// size to look at (roughly 30 cm across) at arm's length.
    static let scale: Float = 0.09

    /// Builds one `ModelEntity` per pentagonal face, each carrying its own
    /// custom pentagon mesh and a text-labeled unlit material. Every face
    /// entity is named `"face_<index>"` and tagged with a `MonthFaceComponent`
    /// so it can be identified later (e.g. for tap handling).
    @MainActor
    static func buildFaceEntities(labels: [FaceLabel]) -> [ModelEntity] {
        precondition(labels.count == faces.count)

        let scaledVertices = vertices.map { $0 * scale }
        let globalUp = SIMD3<Float>(0, 1, 0)

        var entities: [ModelEntity] = []
        entities.reserveCapacity(faces.count)

        for (faceIndex, indices) in faces.enumerated() {
            let positions = indices.map { scaledVertices[$0] }
            let centroid = positions.reduce(SIMD3<Float>.zero, +) / Float(positions.count)

            // Outward normal from the first triangle of the fan.
            let normal = normalize(cross(positions[1] - positions[0], positions[2] - positions[0]))

            // In-plane basis: "v" follows global up as closely as possible so
            // text reads right-side-up on every face; "u" completes a
            // right-handed, normal-facing basis.
            var v = globalUp - dot(globalUp, normal) * normal
            if length(v) < 0.001 {
                // Face normal is nearly parallel to global up (rare, doesn't
                // happen for this orientation, but guarded for robustness).
                v = SIMD3<Float>(0, 0, 1) - dot(SIMD3<Float>(0, 0, 1), normal) * normal
            }
            v = normalize(v)
            let u = normalize(cross(v, normal))

            // Project each vertex into the (u, v) face-local 2D frame and
            // find the pentagon's circumradius so we can map it into a
            // square [0,1]x[0,1] texture with the label centered.
            var local2D: [SIMD2<Float>] = []
            var maxR: Float = 0
            for p in positions {
                let d = p - centroid
                let uv = SIMD2<Float>(dot(d, u), dot(d, v))
                local2D.append(uv)
                maxR = max(maxR, length(uv))
            }
            let uvScale: Float = 1.0 / (2.0 * maxR * 1.05) // 5% margin
            let textureCoords: [SIMD2<Float>] = local2D.map { uv in
                SIMD2<Float>(0.5 + uv.x * uvScale, 0.5 - uv.y * uvScale) // flip V for image space
            }

            var descriptor = MeshDescriptor(name: "face_\(faceIndex)")
            descriptor.positions = MeshBuffers.Positions(positions)
            descriptor.normals = MeshBuffers.Normals(Array(repeating: normal, count: positions.count))
            descriptor.textureCoordinates = MeshBuffers.TextureCoordinates(textureCoords)
            descriptor.primitives = .triangles([
                0, 1, 2,
                0, 2, 3,
                0, 3, 4,
            ])

            let label = labels[faceIndex]
            let material = TextTexture.makeFaceMaterial(month: label.month, year: label.year, emphasized: label.isCurrent)

            guard let mesh = try? MeshResource.generate(from: [descriptor]) else { continue }
            let entity = ModelEntity(mesh: mesh, materials: [material])
            entity.name = "face_\(faceIndex)"

            // Give each face a collision shape + input target so it can be
            // tapped/gazed at. See ImmersiveView for the current minimal
            // handling, and the design discussion for planned behavior.
            entity.components.set(InputTargetComponent())
            entity.components.set(CollisionComponent(shapes: [.generateConvex(from: mesh)]))
            entity.components.set(HoverEffectComponent())
            entity.components.set(MonthFaceComponent(faceIndex: faceIndex, month: label.month, year: label.year))

            entities.append(entity)
        }

        return entities
    }
}

/// A label to draw on one pentagonal face.
struct FaceLabel {
    let month: String
    let year: Int
    /// True only for the single face representing the current month —
    /// used to make it visually stand out (e.g. brighter highlight color).
    let isCurrent: Bool
}

/// Attached to each face entity so future interaction code can look up
/// which month/year a tapped/gazed entity represents without re-parsing
/// its name string.
struct MonthFaceComponent: Component {
    let faceIndex: Int
    let month: String
    let year: Int
}
```

## Response:
> **Artifact: MonthFaceLabeler**
```plaintext
import Foundation

/// Computes the month/year label for every one of the dodecahedron's 12
/// faces, based on today's date.
///
/// Layout (per the spec):
///  - Face `frontFaceIndex`: the current month + current year.
///  - The 5 `frontRing` faces (visible alongside the front face): the
///    previous 5 months, each with its own correct calendar year (so this
///    correctly rolls over a year boundary, e.g. Dec -> Jan).
///  - Face `backFaceIndex` + the 5 `backRing` faces (not visible from the
///    front): the remaining 6 calendar months, all labeled with the
///    *previous* year, per the spec's simplified convention.
enum MonthFaceLabeler {

    private static let monthAbbreviations = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ]

    /// Returns the correct (abbreviation, year) for the month that is
    /// `monthsBack` whole calendar months before `date`.
    private static func monthYear(monthsBack: Int, from date: Date, calendar: Calendar = .current) -> (abbrev: String, year: Int) {
        guard let shifted = calendar.date(byAdding: .month, value: -monthsBack, to: date) else {
            return ("?", 0)
        }
        let comps = calendar.dateComponents([.month, .year], from: shifted)
        let monthIndex = (comps.month ?? 1) - 1 // 0-based
        return (monthAbbreviations[monthIndex], comps.year ?? 0)
    }

    /// Builds the full 12-entry label array, indexed exactly like
    /// `DodecahedronGeometry.faces` (i.e. `labels[i]` is the label for face
    /// `i`).
    static func makeLabels(for date: Date = Date(), calendar: Calendar = .current) -> [FaceLabel] {
        var labels = [FaceLabel?](repeating: nil, count: 12)

        // Front face: current month/year.
        let current = monthYear(monthsBack: 0, from: date, calendar: calendar)
        labels[DodecahedronGeometry.frontFaceIndex] = FaceLabel(month: current.abbrev, year: current.year, isCurrent: true)

        // Front ring: previous 5 months, each with its own correct year.
        for (i, faceIndex) in DodecahedronGeometry.frontRing.enumerated() {
            let monthsBack = i + 1 // 1...5
            let my = monthYear(monthsBack: monthsBack, from: date, calendar: calendar)
            labels[faceIndex] = FaceLabel(month: my.abbrev, year: my.year, isCurrent: false)
        }

        // Previous year, used for every "remaining" face.
        let previousYear = (calendar.dateComponents([.year], from: date).year ?? current.year) - 1

        // Back face: the 6th remaining month (correct month name, year
        // forced to "previous year" per spec).
        let backMonth = monthYear(monthsBack: 6, from: date, calendar: calendar).abbrev
        labels[DodecahedronGeometry.backFaceIndex] = FaceLabel(month: backMonth, year: previousYear, isCurrent: false)

        // Back ring: the remaining 5 months (monthsBack 7...11), same rule.
        for (i, faceIndex) in DodecahedronGeometry.backRing.enumerated() {
            let monthsBack = i + 7 // 7...11
            let month = monthYear(monthsBack: monthsBack, from: date, calendar: calendar).abbrev
            labels[faceIndex] = FaceLabel(month: month, year: previousYear, isCurrent: false)
        }

        return labels.map { $0! }
    }
}
```

## Response:
> **Artifact: TextTexture**
```plaintext
import Foundation
import RealityKit
import UIKit

/// Renders month/year text to a small square image and turns it into a
/// RealityKit material. This is the simplest reliable way to put crisp text
/// on an arbitrary custom mesh (like our pentagon faces) in visionOS today —
/// see the design discussion in README.md for alternatives and trade-offs.
enum TextTexture {

    private static let textureSize = 512

    /// Builds an unlit material showing `month` and `year` stacked on a
    /// rounded, slightly inset card so the pentagon's silhouette stays
    /// legible even though the texture itself is a plain square.
    @MainActor
    static func makeFaceMaterial(month: String, year: Int, emphasized: Bool) -> UnlitMaterial {
        let backgroundColor: UIColor = emphasized
            ? UIColor(red: 0.15, green: 0.35, blue: 0.65, alpha: 1.0)
            : UIColor(white: 0.12, alpha: 1.0)
        let textColor: UIColor = .white

        let image = renderImage(month: month, year: year, background: backgroundColor, textColor: textColor)

        var material = UnlitMaterial()
        if let cgImage = image.cgImage,
           let texture = try? TextureResource(image: cgImage, options: .init(semantic: .color)) {
            material.color = .init(texture: .init(texture))
        } else {
            // Fallback so the app never crashes if texture creation fails
            // (e.g. simulator edge cases) — flat color still shows the face.
            material.color = .init(tint: backgroundColor)
        }
        return material
    }

    @MainActor
    private static func renderImage(month: String, year: Int, background: UIColor, textColor: UIColor) -> UIImage {
        let size = CGSize(width: textureSize, height: textureSize)
        let renderer = UIGraphicsImageRenderer(size: size)

        return renderer.image { ctx in
            background.setFill()
            ctx.fill(CGRect(origin: .zero, size: size))

            let monthFont = UIFont.systemFont(ofSize: 150, weight: .bold)
            let yearFont = UIFont.systemFont(ofSize: 90, weight: .medium)

            let monthAttrs: [NSAttributedString.Key: Any] = [
                .font: monthFont,
                .foregroundColor: textColor,
            ]
            let yearAttrs: [NSAttributedString.Key: Any] = [
                .font: yearFont,
                .foregroundColor: textColor.withAlphaComponent(0.8),
            ]

            let monthString = month as NSString
            let yearString = "\(year)" as NSString

            let monthSize = monthString.size(withAttributes: monthAttrs)
            let yearSize = yearString.size(withAttributes: yearAttrs)
            let spacing: CGFloat = 20
            let totalHeight = monthSize.height + spacing + yearSize.height
            let top = (size.height - totalHeight) / 2

            let monthOrigin = CGPoint(x: (size.width - monthSize.width) / 2, y: top)
            let yearOrigin = CGPoint(x: (size.width - yearSize.width) / 2, y: top + monthSize.height + spacing)

            monthString.draw(at: monthOrigin, withAttributes: monthAttrs)
            yearString.draw(at: yearOrigin, withAttributes: yearAttrs)
        }
    }
}
```

## Response:
> **Artifact: DodecaCalendarApp**
```plaintext
import SwiftUI

@main
struct DodecaCalendarApp: App {

    @State private var immersionStyle: ImmersionStyle = .mixed

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .windowStyle(.plain)

        ImmersiveSpace(id: "DodecaCalendarSpace") {
            ImmersiveView()
        }
        .immersionStyle(selection: $immersionStyle, in: .mixed)
    }
}
```

## Response:
> **Artifact: ContentView**
```plaintext
import SwiftUI

struct ContentView: View {
    @Environment(\.openImmersiveSpace) private var openImmersiveSpace
    @Environment(\.dismissImmersiveSpace) private var dismissImmersiveSpace

    @State private var isImmersiveSpaceOpen = false

    var body: some View {
        VStack(spacing: 24) {
            Image(systemName: "calendar")
                .font(.system(size: 64))
                .foregroundStyle(.tint)

            Text("Month Dodecahedron")
                .font(.largeTitle.bold())

            Text("A twelve-sided calendar. One pentagon faces you, showing the current month. Its five neighbors show the five months before it.")
                .font(.body)
                .multilineTextAlignment(.center)
                .foregroundStyle(.secondary)
                .frame(maxWidth: 420)

            Button(isImmersiveSpaceOpen ? "Hide the Dodecahedron" : "Show the Dodecahedron") {
                Task {
                    if isImmersiveSpaceOpen {
                        await dismissImmersiveSpace()
                        isImmersiveSpaceOpen = false
                    } else {
                        switch await openImmersiveSpace(id: "DodecaCalendarSpace") {
                        case .opened:
                            isImmersiveSpaceOpen = true
                        default:
                            isImmersiveSpaceOpen = false
                        }
                    }
                }
            }
            .font(.title3)
            .buttonStyle(.borderedProminent)
        }
        .padding(48)
    }
}

#Preview {
    ContentView()
}
```

## Response:
> **Artifact: ImmersiveView**
```plaintext
import SwiftUI
import RealityKit

struct ImmersiveView: View {

    /// The face the user most recently tapped, if any. A stand-in for the
    /// "respond somehow using data from that month" behavior described in
    /// the design discussion — right now it just prints and briefly
    /// highlights the face.
    @State private var selectedFaceIndex: Int?

    var body: some View {
        RealityView { content in
            let root = Entity()
            root.name = "DodecaRoot"

            // Positioned ~1.2m in front of, and slightly below, a user
            // standing at the space's origin looking down -Z. Adjust to
            // taste, or anchor to .head for a body-locked version.
            root.position = SIMD3<Float>(0, 1.4, -1.2)

            let labels = MonthFaceLabeler.makeLabels()
            let faceEntities = DodecahedronGeometry.buildFaceEntities(labels: labels)
            for entity in faceEntities {
                root.addChild(entity)
            }

            content.add(root)
        }
        .gesture(
            TapGesture().targetedToAnyEntity().onEnded { value in
                guard let component = value.entity.components[MonthFaceComponent.self] else { return }
                selectedFaceIndex = component.faceIndex

                // --- Extension point for future versions ---
                // This is where a tap would eventually trigger fetching and
                // displaying real data for `component.month` / `component.year`.
                // For now we just log it and nudge the face to confirm the
                // tap registered.
                print("Tapped face \(component.faceIndex): \(component.month) \(component.year)")
                pulse(value.entity)
            }
        )
    }

    /// A tiny scale animation so tapping a face gives immediate feedback,
    /// even before there's real data behind it.
    private func pulse(_ entity: Entity) {
        let original = entity.transform
        var grown = original
        grown.scale *= 1.12

        var animation = Transform.identity
        animation = grown
        entity.move(to: animation, relativeTo: entity.parent, duration: 0.12, timingFunction: .easeOut)

        Task {
            try? await Task.sleep(for: .milliseconds(140))
            entity.move(to: original, relativeTo: entity.parent, duration: 0.18, timingFunction: .easeInOut)
        }
    }
}
```

## Response:
> **Artifact: README**

> # Month Dodecahedron (visionOS)
> 
> A dodecahedron floats about 1.2 m in front of the user. One pentagonal face
> points straight at them and shows the current month + year. Its five
> neighbors — also visible from the front — show the five previous months.
> The six faces on the far side, out of view until the user walks around or
> rotates the object, show the remaining six calendar months labeled with the
> previous year.
> 
> ## Face layout
> 
> | Faces | Content | Visible from front? |
> |---|---|---|
> | Face 0 | Current month + year | Yes (dead ahead) |
> | Faces 5, 2, 1, 7, 8 | Previous 1–5 months, each with its correct year | Yes (ring around face 0) |
> | Face 10 | 6th remaining month, labeled with **previous year** | No (directly opposite face 0) |
> | Faces 6, 9, 11, 3, 4 | Remaining months 7–11 back, labeled with **previous year** | No (ring around face 10) |
> 
> The geometry (which vertices form which face, which faces are adjacent) was
> generated and verified with a small NumPy/SciPy script (convex hull +
> adjacency checks: every vertex touches exactly 3 faces, every edge is shared
> by exactly 2 faces, Euler's formula V−E+F=2 holds) rather than typed in by
> hand, so the mesh is a true regular dodecahedron.
> 
> ## Project setup
> 
> This sandbox can't run Xcode or a visionOS simulator, so these are plain
> Swift source files rather than a buildable `.xcodeproj`. To use them:
> 
> 1. In Xcode, **File → New → Project → visionOS → App**. Choose the "Full
>    Space" or "Mixed" style (either works; the code requests `.mixed`
>    immersion).
> 2. Delete the template's default `ContentView.swift` / app file.
> 3. Drag in `App/`, `Geometry/`, and `Rendering/` from this delivery,
>    keeping the folders as groups.
> 4. Build & run on a Vision Pro simulator or device (visionOS 1.0+).
> 
> No third-party dependencies — just SwiftUI, RealityKit, and UIKit (for text
> rasterization).
> 
> ---
> 
> ## Design discussion: text rendering and future interaction
> 
> ### How text rendering works today, and its limits
> 
> RealityKit doesn't have a built-in "3D text on an arbitrary custom mesh"
> primitive the way SwiftUI has `Text`. The two realistic options are:
> 
> 1. **`MeshResource.generateText`** — RealityKit's extruded 3D text. Good for
>    text that floats in space or sits on a flat rectangular card, but it
>    produces its own separate mesh/entity rather than a decal *on* an
>    existing mesh, so getting it to sit flush on a pentagon and reliably
>    centered would mean a second entity per face plus manual alignment —
>    more moving parts for a non-rectangular target than it saves.
> 2. **Rasterize text into a texture, apply as a material's base color** —
>    what this app does: draw "Jul" / "2026" with `UIGraphicsImageRenderer`
>    into a 512×512 image, wrap it as a `TextureResource`, and map it onto the
>    pentagon via UV coordinates computed from the face's own geometry. This
>    composes naturally with a custom mesh of any shape, and it's cheap
>    (twelve small offscreen renders, once, at launch).
> 
> The trade-off with rasterized text is that it's a fixed-resolution bitmap:
> lean in very close and it will look softer than native vector text would,
> and it doesn't respond to Dynamic Type or the system's text-legibility
> settings the way a SwiftUI `Text` view would. For a dozen short labels on an
> object meant to be viewed from a normal conversational distance, that's a
> reasonable trade against the complexity of the alternatives. If crisper
> close-up text becomes a priority, a middle ground worth prototyping is
> rendering at a higher resolution (e.g. 1024×1024) only for the currently
> front-facing faces, or switching those specific faces to real SwiftUI
> `Attachments` in `RealityView` (see below) once the interaction model needs
> richer content anyway.
> 
> ### Toward month selection: what changes
> 
> The current build already lays the groundwork: every face is a real
> `Entity` with its own `InputTargetComponent`, `CollisionComponent`, and
> `HoverEffectComponent`, tagged with a `MonthFaceComponent` carrying its
> month and year. Tapping one currently just prints to the console and gives
> a small scale "pulse" for feedback. Turning that into "select a month and
> see its data" mainly means designing what happens *after* the tap, since
> the tap itself is already wired up:
> 
> - **Highlighting selection state.** Rather than a one-off pulse, the
>   selected face should probably stay visually distinct (an outline, a
>   brighter material, a subtle glow) until another face is selected or the
>   panel is dismissed — the same treatment the current month already gets,
>   reused as a "you picked this one" state.
> 
> - **Where the data appears.** Vision Pro's spatial UI conventions favor a
>   panel that appears near, but not on top of, the thing that triggered it.
>   RealityKit's `RealityView` supports SwiftUI `Attachments`: ordinary
>   SwiftUI views (so real text, real Dynamic Type, real accessibility) that
>   get a 3D transform and can be anchored just above or beside the selected
>   face. That's a better fit here than trying to cram a chart or list into
>   another rasterized texture — attachments are the natural next step once
>   content is data-driven rather than a static label.
> 
> - **What data, and from where.** "Data from that month" is open-ended by
>   design; a few directions:
>   - *Personal data already on-device*: calendar event counts, photo
>     highlights, screen-time, fitness history for that month via
>     EventKit/PhotoKit/HealthKit — no network needed, and immediately useful.
>   - *An app-specific dataset*: if this is a journal, budget, or habit
>     tracker, the month face becomes a natural entry point into that month's
>     records.
>   - *Remote data*: financial, weather, or usage statistics for that period,
>     fetched asynchronously — in which case the attachment should show a
>     loading state immediately on tap rather than waiting for the network
>     before responding at all, since instant tap feedback matters more in a
>     spatial UI than it does on a flat screen.
> 
> - **Navigation model.** A single tap could either (a) open a lightweight
>   summary attachment right there, with a secondary action to "go deeper," or
>   (b) immediately replace the 2D window's content with that month's full
>   view. (a) keeps the user immersed and is likely the better default; (b)
>   suits a case where the dodecahedron is explicitly a month *picker* for a
>   separate, more detailed app.
> 
> - **Discoverability of the back six faces.** Since six months are only
>   reachable by walking around or manually rotating the object, a future
>   version should make that discoverable — a subtle continuous rotation when
>   idle, a drag gesture to spin it, or both — otherwise users may not realize
>   five months ago isn't the whole story.
> 
> None of this requires re-deriving the geometry; it's additive on top of the
> `MonthFaceComponent` and tap handling already in `ImmersiveView.swift`.

## Prompt:
How do I resolve this error: Unable to open an immersive space when the app does not support multiple scenes. Set UIApplicationSupportsMultipleScenes to YES in the UIApplicationSceneManifest dictionary in your Info.plist to indicate that your app supports displaying two or more scenes simultaneously.

## Response:
That error is a project-configuration issue, not a code bug — visionOS requires you to explicitly declare that your app can show more than one scene at once (the 2D window *and* the immersive space), and new projects don't always have that turned on by default.

**Fix: add `UIApplicationSupportsMultipleScenes = YES`**

**If your target uses an actual `Info.plist` file:**

1. Find `Info.plist` in the project navigator (or under your target's Build Settings → search "Info.plist File" to see its path).
2. Right-click it → **Open As → Source Code**.
3. Add this inside the outer `<dict>`:

```xml
<key>UIApplicationSceneManifest</key>
<dict>
    <key>UIApplicationSupportsMultipleScenes</key>
    <true/>
</dict>
```

(If `UIApplicationSceneManifest` already exists, just add the `UIApplicationSupportsMultipleScenes` key/value pair inside it rather than duplicating the outer dict.)

**If your target has no `Info.plist` file (Xcode auto-generates it — check Build Settings → "Generate Info.plist File" = Yes):**

1. Select your target → **Info** tab.
2. Hover over any row → click **+** → add key **"Application Scene Manifest"** (this is `UIApplicationSceneManifest`), type Dictionary.
3. Expand it → add a child row **"Enable Multiple Windows"** (this is `UIApplicationSupportsMultipleScenes`), type Boolean, value **YES**.

Then clean build (⇧⌘K) and run again.

One thing worth double-checking: make sure you didn't remove the `WindowGroup` from `DodecaCalendarApp.swift` — the app needs both the `WindowGroup` and the `ImmersiveSpace` declared in `body` (which the file I gave you does) for this setting to make sense; a pure immersive-only app that never shows a 2D window wouldn't need it.

## Prompt:
it got this error: /Library/Caches/com.apple.xbs/3FAFE707-3D32-45AE-B5F3-E2E8CDF33A78/TemporaryDirectory.dr5wmA/Sources/REKit_Sim/ThirdParty/PhysX/physx/source/physxcooking/src/convex/QuickHullConvexHullLib.cpp (935) : internal error : QuickHullConvexHullLib::findSimplex: Simplex input points appers to be coplanar.

Failed to cook convex mesh (0x3)

## Response:
Good catch — that error is because PhysX's convex-hull cooker needs a real 3D volume, but each pentagon face is perfectly flat (all 5 points lie in one plane), so it has no "simplex" to build a hull from. `generateConvex(from: mesh)` is the wrong collision-shape source for a flat mesh.

**Fix:** give the collision shape a tiny bit of thickness by extruding the 5 vertices slightly along the face normal before building the convex shape, and build it from raw points instead of the mesh.

Replace that one file and rebuild. The `mesh` variable (used for rendering) is untouched — only the collision shape's source data changed, so the visuals stay exactly the same, but PhysX now has actual volume to cook a hull from.

## Prompt:
The text labels show upside down.  What is the possible cause of this?

## Response:
The most likely cause is a **top/bottom mismatch between two coordinate conventions that both got flipped**, so instead of canceling out they compounded (or one was simply backwards):

1. **The mesh's V coordinate** — in `DodecahedronGeometry.swift` I computed `textureCoords.y = 0.5 - uv.y * uvScale`, deliberately flipping the "up" direction because I assumed RealityKit's texture-V axis runs top-to-bottom like a typical image buffer.
2. **The texture image itself** — `UIGraphicsImageRenderer`/`CGContext` also draws in a top-left-origin space (y increases downward), which is where "Jul" actually got drawn.

If RealityKit's mesh UV convention doesn't match what I assumed in step 1 (i.e., V=0 is actually the *bottom* of the texture rather than the top), then my manual flip pushes the "up" vertices to the wrong end of the image, and the label renders inverted.

**The fix** — flip the sign in that one line so "up" in 3D maps to the other end of V:

A couple of notes since I can't test this in a simulator myself:

- **If this over-corrects** (text now upside down in the *other* direction, or was actually fine before and something else was the culprit), the other common culprit is that `TextureResource(image: cgImage, ...)` itself gets flipped depending on the `CGImage`'s row order — in that case, revert this line and instead vertically flip the image in `TextTexture.swift` by drawing with a flipped `CGContext` transform.
- **If it's mirrored left-right** instead of (or in addition to) upside-down, that's a separate issue — it'd mean the `u` basis vector needs negating, not `v`.

Since these UV/image-origin conventions are notoriously easy to get backwards and I don't have a way to render and check visually from here, if flipping the sign doesn't fully fix it, tell me exactly what you're seeing (upside down, mirrored, or rotated 90°) and I can narrow down which of the two flips is wrong.

## Prompt:
The year for January shows 2025.  It should be 2026.  Where does this change get made?

## Response:
That happens because of a deliberate simplification in `MonthFaceLabeler.swift`: instead of calculating each "remaining" face's actual calendar year, the code forces **all six** of them to `currentYear - 1`. For January that's wrong — January is only 6 months before July, so it actually falls in 2026, not 2025. The "force previous year" rule only happens to be correct for August–December, not for January.

**The fix** is in `Geometry/MonthFaceLabeler.swift` — stop overriding the year and just use the correctly-computed year for every face, the same way the front ring already does:

Also updating the header comment, since it described the old (incorrect) behavior:

With today's date, this now gives every face its true rolling-calendar year: Jul 2026 (front) → Jun–Feb 2026 (front ring) → Jan 2026, Dec–Aug 2025 (back six). Only August through December end up in 2025; January correctly stays in 2026.

## Prompt:
When you make a recording in the VisionOS simulator where does it get saved?

## Response:
Same mechanism as the iOS/iPadOS Simulator, since visionOS simulator runs in the same Simulator.app: it defaults to your **Desktop**.

- Use **File → Record Screen** (or ⌘R) in the Simulator's menu bar to start; stopping shows a preview, then the file is saved as an `.mp4` to your Desktop.
- To save somewhere else without changing the default every time, **hold the Option key** when clicking Record (or when stopping) to pick a destination folder.
- If you'd rather script it or set a specific path directly, use `simctl` from Terminal instead:
```
xcrun simctl io booted recordVideo ~/Desktop/dodeca-demo.mov
```
Press **Ctrl+C** in Terminal to stop that recording. This works against whichever simulator is currently booted — including the Vision Pro simulator — since `simctl` isn't OS-specific.

One caveat worth knowing for your app specifically: simulator recordings capture the flat window view of the visionOS simulator (the 2D "look through the headset" preview), not a true stereoscopic capture — fine for sharing a quick demo of the dodecahedron, but not representative of how depth/immersion actually looks on-device.

