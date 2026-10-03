// hmtrace — resolve hm:// links the way Origami Text does
// (AppModel.openHypermediaURL → HypermediaFetcher.fetch → presentHypermedia)
// and write every step, request and response summary to a text file.
//
// Build:  swiftc -O -swift-version 5 main.swift -o hmtrace
// Run:    ./hmtrace --out trace.txt "hm://z6Mk.../some-path"
//         ./hmtrace --space example.org --comments "hm://z6Mk.../a" "hm://z6Mk.../a"
//
// Logic is ported from HypermediaFetcher.swift and HypermediaOpen.swift:
//   OPTIONS https://space/        → x-hypermedia-id / -title   (space identity)
//   GET     https://space/api/Resource?id=<hm://uid/path[?v=]>   (a document)
//   GET     https://space/api/Account?id=<uid>                   (author names)
//   GET     https://space/api/ListComments?targetId=<json>       (comments)
// Responses are SuperJSON: {"json": <payload>, "meta": …}.
//
// Not reproduced: LiquidDoc construction, LiquidAddress.makeID, inline
// annotation rendering. The trace says where those would happen.
// This file has not been compiled or run against a live server.

import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

// MARK: - Trace

final class Trace: @unchecked Sendable {
    private var lines: [String] = []
    private var count = 0
    private let start = Date()

    func step(_ title: String) {
        count += 1
        let t = String(format: "%7.3fs", Date().timeIntervalSince(start))
        emit("[\(t)] STEP \(count): \(title)")
    }
    func note(_ text: String) { emit("            · \(text)") }
    func blank() { emit("") }
    private func emit(_ s: String) { lines.append(s); print(s) }

    func write(to path: String) {
        do { try (lines.joined(separator: "\n") + "\n").write(toFile: path, atomically: true, encoding: .utf8) }
        catch { FileHandle.standardError.write(Data("Could not write \(path): \(error)\n".utf8)) }
    }
}


/// Shared state lives in a plain type, not in top-level variables: in a
/// file with top-level `await`, top-level variables are main-actor isolated.
final class NameCache: @unchecked Sendable {
    var names: [String: String] = [:]
}

enum Globals {
    static let trace = Trace()
    static let nameCache = NameCache()
    static let gatewayDomain = "hyper.media"
}

// MARK: - Errors (messages as in HypermediaError)

enum HMError: Error, CustomStringConvertible {
    case invalidAddress
    case notASpace(String)
    case httpError(Int)
    case notFound(address: String, spaces: [String])
    case isComment
    case isDeleted
    case serverError(String)
    case decodingFailed(String)

    var description: String {
        switch self {
        case .invalidAddress: return "That is not a Hypermedia address."
        case .notASpace(let d): return "\(d) does not answer as a Hypermedia space."
        case .httpError(let c): return "The space returned HTTP \(c)."
        case .notFound(let a, let s):
            return s.isEmpty ? "No document at \(a)." : "No document at \(a) on \(s.joined(separator: ", "))."
        case .isComment: return "That address is a comment, which Origami Text cannot open yet."
        case .isDeleted: return "That document has been deleted."
        case .serverError(let m): return "The space reported an error: \(m)"
        case .decodingFailed(let d): return "Could not read the document: \(d)"
        }
    }
}

// MARK: - Address (ported from HypermediaAddress)

struct HMAddress {
    let uid: String
    let path: [String]
    let version: String?
    let blockRef: String?
    let origin: URL?

    var canonicalID: String {
        path.isEmpty ? "hm://\(uid)" : "hm://\(uid)/\(path.joined(separator: "/"))"
    }
    var resourceID: String {
        version.map { "\(canonicalID)?v=\($0)" } ?? canonicalID
    }

    private static let staticGatewayPaths: Set<String> = ["download", "connect", "register", "profile", "contact", "api"]

    static func parse(_ string: String) -> HMAddress? {
        let trimmed = string.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let schemeRange = trimmed.range(of: "://") else { return nil }
        let scheme = trimmed[..<schemeRange.lowerBound].lowercased()
        var rest = String(trimmed[schemeRange.upperBound...])

        var fragment: String?
        if let hash = rest.firstIndex(of: "#") {
            fragment = String(rest[rest.index(after: hash)...])
            rest = String(rest[..<hash])
        }
        var query: [String: String] = [:]
        if let q = rest.firstIndex(of: "?") {
            let queryString = String(rest[rest.index(after: q)...])
            rest = String(rest[..<q])
            for pair in queryString.split(separator: "&") {
                let parts = pair.split(separator: "=", maxSplits: 1, omittingEmptySubsequences: false)
                let key = String(parts[0])
                let value = parts.count > 1 ? String(parts[1]) : ""
                query[key] = value.removingPercentEncoding ?? value
            }
        }
        let segments = rest.split(separator: "/", omittingEmptySubsequences: false).map(String.init)

        let uid: String
        let path: [String]
        var origin: URL?
        switch scheme {
        case "hm":
            guard let first = segments.first, !first.isEmpty else { return nil }
            uid = first
            path = segments.dropFirst().filter { !$0.isEmpty }
        case "https", "http":
            guard segments.count >= 3, segments[1] == "hm" else { return nil }
            let host = segments[0]
            guard !host.isEmpty, !segments[2].isEmpty,
                  !staticGatewayPaths.contains(segments[2].lowercased()) else { return nil }
            uid = segments[2]
            path = segments.dropFirst(3).filter { !$0.isEmpty }
            origin = URL(string: "\(scheme)://\(host)")
        default:
            return nil
        }
        let version = query["v"].flatMap { $0.isEmpty ? nil : $0 }
        return HMAddress(uid: uid, path: path, version: version,
                         blockRef: blockID(fromFragment: fragment), origin: origin)
    }

    /// `id`, `id+`, `id[3:9]` → `id`.
    static func blockID(fromFragment fragment: String?) -> String? {
        guard var fragment, !fragment.isEmpty else { return nil }
        if let bracket = fragment.firstIndex(of: "[") { fragment = String(fragment[..<bracket]) }
        if fragment.hasSuffix("+") { fragment.removeLast() }
        return fragment.isEmpty ? nil : fragment
    }
}

struct HMSpace {
    let domain: String
    let uid: String
    let title: String
    var origin: URL { URL(string: "https://\(domain)")! }
}


// MARK: - HTTP with logging

func request(_ method: String, _ url: URL, accept: String?) async throws -> (Data, HTTPURLResponse) {
    var req = URLRequest(url: url)
    req.httpMethod = method
    req.timeoutInterval = method == "GET" ? 30 : 20
    if let accept { req.setValue(accept, forHTTPHeaderField: "Accept") }
    Globals.trace.note("→ \(method) \(url.absoluteString)")
    let t0 = Date()
    do {
        let (data, response) = try await URLSession.shared.data(for: req)
        guard let http = response as? HTTPURLResponse else {
            Globals.trace.note("✗ response was not HTTP")
            throw HMError.invalidAddress
        }
        let ms = Int(Date().timeIntervalSince(t0) * 1000)
        Globals.trace.note("← HTTP \(http.statusCode), \(data.count) bytes, \(ms) ms")
        let headers = http.allHeaderFields.compactMap { k, v -> (String, String)? in
            guard let key = (k as? String)?.lowercased(), let val = v as? String else { return nil }
            return (key, val)
        }.sorted { $0.0 < $1.0 }
        for (k, v) in headers where k.hasPrefix("x-hypermedia-") || k == "content-type" {
            Globals.trace.note("  header \(k): \(v.removingPercentEncoding ?? v)")
        }
        return (data, http)
    } catch {
        if !(error is HMError) { Globals.trace.note("✗ transport error: \(error.localizedDescription)") }
        throw error
    }
}

/// HypermediaFetcher.get: JSON GET, non-2xx → httpError.
func get(_ url: URL) async throws -> Data {
    let (data, http) = try await request("GET", url, accept: "application/json")
    if !(200...299).contains(http.statusCode) { throw HMError.httpError(http.statusCode) }
    return data
}

/// HypermediaFetcher.hypermediaHeaders: OPTIONS, x-hypermedia-* only.
func hypermediaHeaders(for url: URL) async throws -> [String: String] {
    let (_, http) = try await request("OPTIONS", url, accept: nil)
    guard (200...299).contains(http.statusCode) else {
        Globals.trace.note("non-2xx answer to OPTIONS: treated as \"no Hypermedia headers\"")
        return [:]
    }
    var out: [String: String] = [:]
    for (key, value) in http.allHeaderFields {
        guard let name = (key as? String)?.lowercased(), name.hasPrefix("x-hypermedia-"),
              let raw = value as? String else { continue }
        out[name] = raw.removingPercentEncoding ?? raw
    }
    if out.isEmpty { Globals.trace.note("no x-hypermedia-* headers present") }
    return out
}

/// The SuperJSON envelope: {"json": payload}.
func payload(_ data: Data, what: String) throws -> [String: Any] {
    do {
        guard let root = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let json = root["json"] as? [String: Any] else {
            throw HMError.decodingFailed("empty \(what)")
        }
        return json
    } catch let e as HMError { throw e }
    catch { throw HMError.decodingFailed(error.localizedDescription) }
}

// MARK: - Space identity

func resolveSpace(domain raw: String) async throws -> HMSpace {
    var s = raw.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
    if let r = s.range(of: "://") { s = String(s[r.upperBound...]) }
    if let slash = s.firstIndex(of: "/") { s = String(s[..<slash]) }
    guard !s.isEmpty, let url = URL(string: "https://\(s)/") else { throw HMError.invalidAddress }
    let headers = try await hypermediaHeaders(for: url)
    guard let id = headers["x-hypermedia-id"], let address = HMAddress.parse(id) else {
        throw HMError.notASpace(s)
    }
    let title = headers["x-hypermedia-title"].flatMap { $0.isEmpty ? nil : $0 } ?? s
    return HMSpace(domain: s, uid: address.uid, title: title)
}

// MARK: - Document model (just what the trace reports)

struct FetchResult {
    let title: String
    let author: String
    let canonicalID: String
    let origin: URL
    let created: String
    let version: String
    let paragraphIDs: [(id: String, kind: String)]
    let blockCount: Int
}

func humanize(_ segment: String) -> String {
    let words = segment.replacingOccurrences(of: "-", with: " ")
        .replacingOccurrences(of: "_", with: " ")
        .trimmingCharacters(in: .whitespaces)
    guard let first = words.first else { return segment }
    return first.uppercased() + words.dropFirst()
}

func joinNames(_ names: [String]) -> String {
    switch names.count {
    case 0: return "Unknown"
    case 1: return names[0]
    default: return names.dropLast().joined(separator: ", ") + " and " + names[names.count - 1]
    }
}

/// Mirrors HypermediaFetcher.paragraphs(from:): which blocks become
/// paragraphs, and under what ID (block id, or p<N> when it has none).
func walkBlocks(_ nodes: [[String: Any]]) -> (paragraphs: [(id: String, kind: String)], total: Int) {
    var out: [(id: String, kind: String)] = []
    var total = 0
    var counter = 0
    func process(_ node: [String: Any]) {
        guard let b = node["block"] as? [String: Any] else { return }
        total += 1
        let type = b["type"] as? String ?? "Paragraph"
        let text = b["text"] as? String ?? ""
        let link = b["link"] as? String ?? ""
        let hasText = !text.trimmingCharacters(in: .whitespaces).isEmpty
        let produces: Bool
        switch type {
        case "Heading", "Paragraph": produces = hasText
        case "Code", "Math": produces = !text.isEmpty
        case "Image", "Video", "File", "Embed": produces = !link.isEmpty
        default: produces = hasText || !link.isEmpty
        }
        if produces {
            counter += 1
            let id = (b["id"] as? String).flatMap { $0.isEmpty ? nil : $0 } ?? "p\(counter)"
            out.append((id, type))
        }
        for child in (node["children"] as? [[String: Any]]) ?? [] { process(child) }
    }
    for n in nodes { process(n) }
    return (out, total)
}

// MARK: - Author names


func accountName(uid: String, origin: URL) async -> String? {
    let key = "\(origin.absoluteString)|\(uid)"
    if let cached = Globals.nameCache.names[key] { Globals.trace.note("author name for \(uid.prefix(8))… from session cache: \(cached)"); return cached }
    var comps = URLComponents(url: origin, resolvingAgainstBaseURL: false)
    comps?.path = "/api/Account"
    comps?.queryItems = [URLQueryItem(name: "id", value: uid)]
    guard let url = comps?.url, let data = try? await get(url),
          let json = try? payload(data, what: "account"),
          let meta = json["metadata"] as? [String: Any],
          let name = (meta["name"] as? String)?.trimmingCharacters(in: .whitespaces), !name.isEmpty else {
        Globals.trace.note("no usable name for \(uid.prefix(8))…; will show the uid prefix")
        return nil
    }
    Globals.nameCache.names[key] = name
    return name
}

func authorName(for document: [String: Any], origin: URL) async -> String {
    let metadata = document["metadata"] as? [String: Any]
    if let byline = (metadata?["displayAuthor"] as? String)?.trimmingCharacters(in: .whitespaces), !byline.isEmpty {
        Globals.trace.note("author: metadata.displayAuthor = \"\(byline)\" (no lookup needed)")
        return byline
    }
    var uids = ((document["authors"] as? [String]) ?? []).filter { !$0.isEmpty }
    if uids.isEmpty, let account = document["account"] as? String, !account.isEmpty { uids = [account] }
    guard !uids.isEmpty else { Globals.trace.note("author: none listed → \"Unknown\""); return "Unknown" }
    Globals.trace.note("author: looking up \(min(uids.count, 4)) of \(uids.count) author uid(s)")
    var names: [String] = []
    for uid in uids.prefix(4) { names.append(await accountName(uid: uid, origin: origin) ?? String(uid.prefix(8))) }
    if uids.count > 4 { names.append("others") }
    return joinNames(names)
}

// MARK: - Fetch one document from one space (HypermediaFetcher.fetch(address:origin:))

func fetchDocument(address: HMAddress, origin: URL, allowRedirect: Bool = true) async throws -> FetchResult {
    var comps = URLComponents(url: origin, resolvingAgainstBaseURL: false)
    comps?.path = "/api/Resource"
    comps?.queryItems = [URLQueryItem(name: "id", value: address.resourceID)]
    guard let url = comps?.url else { throw HMError.invalidAddress }
    let data = try await get(url)
    let wrapper = try payload(data, what: "response")
    let siteName = origin.host ?? origin.absoluteString
    let type = wrapper["type"] as? String ?? ""
    Globals.trace.note("resource type: \"\(type)\"")

    if !allowRedirect && type != "document" {
        throw HMError.notFound(address: address.canonicalID, spaces: [origin.host ?? ""])
    }
    switch type {
    case "document":
        guard let document = wrapper["document"] as? [String: Any] else {
            throw HMError.decodingFailed("document missing")
        }
        let author = await authorName(for: document, origin: origin)
        // convert(document:address:origin:author:)
        let metadata = document["metadata"] as? [String: Any]
        let title = (metadata?["name"] as? String).flatMap { $0.isEmpty ? nil : $0 }
            ?? (address.path.last.map(humanize) ?? "Untitled Document")
        let content = (document["content"] as? [[String: Any]]) ?? []
        let walked = walkBlocks(content)
        return FetchResult(title: title, author: author, canonicalID: address.canonicalID, origin: origin,
                           created: (document["createTime"] as? String) ?? "(none; the app uses now)",
                           version: (document["version"] as? String) ?? "",
                           paragraphIDs: walked.paragraphs, blockCount: walked.total)
    case "redirect":
        guard let target = wrapper["redirectTarget"] as? [String: Any],
              let uid = target["uid"] as? String, !uid.isEmpty else {
            throw HMError.notFound(address: address.canonicalID, spaces: [siteName])
        }
        let next = HMAddress(uid: uid, path: (target["path"] as? [String]) ?? [], version: nil,
                             blockRef: address.blockRef, origin: origin)
        Globals.trace.note("redirect → \(next.canonicalID); following once (a second redirect is not chased)")
        return try await fetchDocument(address: next, origin: origin, allowRedirect: false)
    case "not-found": throw HMError.notFound(address: address.canonicalID, spaces: [siteName])
    case "comment":   throw HMError.isComment
    case "tombstone": throw HMError.isDeleted
    case "error":     throw HMError.serverError((wrapper["message"] as? String) ?? "unknown error")
    default:          throw HMError.decodingFailed("unexpected resource type “\(type)”")
    }
}

// MARK: - HypermediaFetcher.fetch(urlString:spaces:)

func fetchURL(_ urlString: String, spaces: [HMSpace]) async throws -> FetchResult {
    let trimmed = urlString.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !trimmed.isEmpty else { throw HMError.invalidAddress }

    if let address = HMAddress.parse(trimmed) {
        if let origin = address.origin {
            Globals.trace.note("address carries its own origin (\(origin.absoluteString)); asking only that server")
            return try await fetchDocument(address: address, origin: origin)
        }
        // Origin order: space listing this uid, other followed spaces, gateway.
        var origins = spaces.filter { $0.uid == address.uid }.map(\.origin)
        let matching = origins.count
        origins += spaces.filter { $0.uid != address.uid }.map(\.origin)
        if !origins.contains(where: { $0.host == Globals.gatewayDomain }) {
            origins.append(URL(string: "https://\(Globals.gatewayDomain)")!)
        }
        Globals.trace.note("bare hm:// address: \(matching) followed space(s) match the uid")
        Globals.trace.note("origins to try, in order: \(origins.compactMap(\.host).joined(separator: " → "))")

        var lastError: Error = HMError.notFound(address: address.canonicalID, spaces: origins.compactMap(\.host))
        for (i, origin) in origins.enumerated() {
            Globals.trace.note("attempt \(i + 1)/\(origins.count): \(origin.host ?? origin.absoluteString)")
            do {
                return try await fetchDocument(address: address, origin: origin)
            } catch HMError.notFound {
                Globals.trace.note("not found on \(origin.host ?? "?"); trying the next origin")
                continue
            } catch {
                Globals.trace.note("error on \(origin.host ?? "?"): \(error); remembered, trying the next origin")
                lastError = error
            }
        }
        if case HMError.notFound = lastError { throw lastError }
        // As in the app: any other last error is reported as not-found.
        Globals.trace.note("all origins failed; the app reports this as \"not found\" even if the last error was different")
        throw HMError.notFound(address: address.canonicalID, spaces: origins.compactMap(\.host))
    }

    // Not an hm address: a page on a space, which says which document it is.
    Globals.trace.note("not an hm:// or gateway address; treating as a page on a space")
    guard let url = URL(string: trimmed), let scheme = url.scheme?.lowercased(),
          scheme == "https" || scheme == "http", let host = url.host else { throw HMError.invalidAddress }
    let headers = try await hypermediaHeaders(for: url)
    guard let id = headers["x-hypermedia-id"], var address = HMAddress.parse(id) else {
        throw HMError.notASpace(host)
    }
    if let comps = URLComponents(url: url, resolvingAgainstBaseURL: false) {
        let version = comps.queryItems?.first(where: { $0.name == "v" })?.value
        address = HMAddress(uid: address.uid, path: address.path, version: version ?? address.version,
                            blockRef: HMAddress.blockID(fromFragment: comps.fragment),
                            origin: URL(string: "\(scheme)://\(host)"))
    }
    return try await fetchDocument(address: address, origin: address.origin ?? URL(string: "https://\(host)")!)
}

// MARK: - Comments (HypermediaFetcher.listComments)

func traceComments(address: HMAddress, origin: URL) async {
    let pathJSON = address.path.map { "\"\($0.replacingOccurrences(of: "\"", with: "\\\""))\"" }.joined(separator: ",")
    let targetID = "{\"id\":\"\(address.canonicalID)\",\"uid\":\"\(address.uid)\",\"path\":[\(pathJSON)],"
        + "\"version\":null,\"blockRef\":null,\"blockRange\":null,\"hostname\":null,\"scheme\":\"hm\",\"latest\":true}"
    var comps = URLComponents(url: origin, resolvingAgainstBaseURL: false)
    comps?.path = "/api/ListComments"
    comps?.queryItems = [URLQueryItem(name: "targetId", value: targetID)]
    guard let url = comps?.url else { Globals.trace.note("could not build the ListComments URL"); return }
    do {
        let json = try payload(try await get(url), what: "comments")
        let comments = (json["comments"] as? [[String: Any]]) ?? []
        let authors = (json["authors"] as? [String: Any]) ?? [:]
        let ids = Set(comments.compactMap { $0["id"] as? String })
        let replies = comments.filter {
            if let p = $0["replyParent"] as? String, !p.isEmpty, ids.contains(p) { return true }
            return false
        }
        Globals.trace.note("\(comments.count) comment(s): \(comments.count - replies.count) top-level, \(replies.count) repl\(replies.count == 1 ? "y" : "ies")")
        for c in comments {
            let uid = c["author"] as? String ?? ""
            let meta = (authors[uid] as? [String: Any])?["metadata"] as? [String: Any]
            let name = (meta?["name"] as? String).flatMap { $0.isEmpty ? nil : $0 } ?? String(uid.prefix(8))
            let paras = walkBlocks((c["content"] as? [[String: Any]]) ?? []).paragraphs.count
            let when = (c["createTime"] as? String) ?? "(no time)"
            let isReply = (c["replyParent"] as? String).map { !$0.isEmpty } ?? false
            Globals.trace.note("  \(isReply ? "↳ reply" : "comment") by \(name), \(when), \(paras) paragraph(s)")
        }
    } catch {
        Globals.trace.note("✗ comments failed: \(error) (the view would show this message)")
    }
}

// MARK: - Cache (HypermediaSpaces.cacheDocument: 24 entries, oldest evicted)

struct CachedDoc { let canonicalID: String; let title: String; let origin: URL; let version: String }

final class DocCache {
    private(set) var docs: [String: CachedDoc] = [:]
    private var order: [String] = []
    func insert(_ doc: CachedDoc) {
        if docs[doc.canonicalID] == nil { order.append(doc.canonicalID) }
        docs[doc.canonicalID] = doc
        Globals.trace.note("cache now holds \(docs.count) document(s)")
        while order.count > 24 {
            let evicted = order.removeFirst()
            docs[evicted] = nil
            Globals.trace.note("evicted oldest entry: \(evicted)")
        }
    }
}

// MARK: - The flow (HypermediaOpen.openHypermediaURL / presentHypermedia)

func openHypermediaURL(_ input: String, spaces: [HMSpace], cache: DocCache, withComments: Bool) async {
    Globals.trace.step("openHypermediaURL called")
    Globals.trace.note("input: \(input)")

    Globals.trace.step("Parse the address (HypermediaAddress.parse)")
    let address = HMAddress.parse(input)
    if let a = address {
        Globals.trace.note("uid:         \(a.uid)")
        Globals.trace.note("path:        \(a.path.isEmpty ? "(root document)" : a.path.joined(separator: "/"))")
        Globals.trace.note("version:     \(a.version ?? "none (latest)")")
        Globals.trace.note("block ref:   \(a.blockRef ?? "none")")
        Globals.trace.note("origin:      \(a.origin?.absoluteString ?? "none (bare hm:// address)")")
        Globals.trace.note("canonicalID: \(a.canonicalID)")
        Globals.trace.note("resourceID:  \(a.resourceID)")
    } else {
        Globals.trace.note("not an hm:// or gateway address; the fetcher will try it as a page on a space")
    }

    Globals.trace.step("Check the document cache by canonical ID")
    if let a = address, let hit = cache.docs[a.canonicalID] {
        Globals.trace.note("HIT: \"\(hit.title)\" → open(cached, fragment: \(a.blockRef ?? "nil")); flow ends")
        return
    }
    Globals.trace.note("MISS (cache holds \(cache.docs.count) document(s))")

    Globals.trace.step("Choose the label for the \"Fetching from …\" note")
    let label: String
    if let host = address?.origin?.host { label = host; Globals.trace.note("source: the address's own origin") }
    else if let first = spaces.first { label = first.domain; Globals.trace.note("source: first followed space") }
    else { label = Globals.gatewayDomain; Globals.trace.note("source: gateway domain") }
    Globals.trace.note("showNote(\"Fetching from \(label)…\") — cosmetic; the real order is decided in the next step")

    Globals.trace.step("HypermediaFetcher.fetch(urlString:spaces:)")
    let result: FetchResult
    do {
        result = try await fetchURL(input, spaces: spaces)
        Globals.trace.note("FetchResult: title=\"\(result.title)\", author=\"\(result.author)\"")
        Globals.trace.note("canonicalID=\(result.canonicalID), origin=\(result.origin.host ?? "?"), version=\(result.version.isEmpty ? "(empty)" : result.version)")
        Globals.trace.note("created: \(result.created)")
        Globals.trace.note("\(result.blockCount) block(s) → \(result.paragraphIDs.count) paragraph(s)")
        for p in result.paragraphIDs.prefix(8) { Globals.trace.note("  paragraph id \(p.id)  (\(p.kind))") }
        if result.paragraphIDs.count > 8 { Globals.trace.note("  … \(result.paragraphIDs.count - 8) more") }
    } catch {
        Globals.trace.step("FAILED — showNote(error.localizedDescription)")
        Globals.trace.note("\(error)")
        Globals.trace.note("nothing cached, no document opened")
        return
    }

    Globals.trace.step("Work out the fragment to land on")
    let fragment = address?.blockRef ?? HMAddress.blockID(fromFragment: URL(string: input)?.fragment)
    Globals.trace.note("fragment: \(fragment ?? "nil (open at top)")")
    if let f = fragment {
        let found = result.paragraphIDs.contains { $0.id == f }
        Globals.trace.note(found ? "paragraph \(f) exists in the fetched document" : "paragraph \(f) NOT found in the fetched document; the reader would open at the top")
    }

    Globals.trace.step("presentHypermedia")
    if let hit = cache.docs[result.canonicalID] {
        Globals.trace.note("second cache check HIT on \(hit.canonicalID); open and stop")
        return
    }
    Globals.trace.note("second cache check MISS")
    Globals.trace.note("would build LiquidDoc: sourceURL=\(result.canonicalID), fileURL=<temp>/Hypermedia/<id>.origamitext (never written)")
    Globals.trace.note("unique document ID via LiquidAddress.makeID is not reproduced here")
    cache.insert(CachedDoc(canonicalID: result.canonicalID, title: result.title,
                           origin: result.origin, version: result.version))
    Globals.trace.note("open(doc, fragment: \(fragment ?? "nil"))")

    if withComments, let a = HMAddress.parse(result.canonicalID) {
        Globals.trace.step("Comments: loadCommentsIfNeeded → refreshComments")
        Globals.trace.note("origin: documentOrigins[id] = \(result.origin.host ?? "?")")
        await traceComments(address: a, origin: result.origin)
    }
}

// MARK: - main

var urls: [String] = []
var outPath = "hm-trace.txt"
var spaceDomains: [String] = []
var withComments = false

var args = CommandLine.arguments.dropFirst().makeIterator()
while let arg = args.next() {
    switch arg {
    case "--out":      outPath = args.next() ?? outPath
    case "--space":    if let s = args.next() { spaceDomains.append(s) }
    case "--comments": withComments = true
    default:           urls.append(arg)
    }
}

guard !urls.isEmpty else {
    print("usage: hmtrace [--out file] [--space domain]… [--comments] <hm-url>…")
    exit(2)
}

Globals.trace.step("Session start")
Globals.trace.note("date: \(ISO8601DateFormatter().string(from: Date()))")
Globals.trace.note("gateway: \(Globals.gatewayDomain)")

var spaces: [HMSpace] = []
if spaceDomains.isEmpty {
    Globals.trace.note("followed spaces: none")
} else {
    Globals.trace.step("Follow spaces (HypermediaFetcher.resolveSpace)")
    for domain in spaceDomains {
        do {
            let space = try await resolveSpace(domain: domain)
            spaces.append(space)
            Globals.trace.note("followed \(space.domain): uid=\(space.uid), title=\"\(space.title)\"")
        } catch {
            Globals.trace.note("could not follow \(domain): \(error)")
        }
    }
}

let cache = DocCache()
for url in urls {
    Globals.trace.blank()
    await openHypermediaURL(url, spaces: spaces, cache: cache, withComments: withComments)
}
Globals.trace.write(to: outPath)
print("\nTrace written to \(outPath)")
