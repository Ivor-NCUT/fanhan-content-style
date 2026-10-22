// macOS native rendering keeps Chinese glyphs sharp without additional dependencies.
import Foundation
import AppKit
import CoreText
import CryptoKit

struct Post: Decodable { let title: String; let body: String; let lines: [String]; let subtitle: String }
func require(_ ok: Bool, _ message: String) throws { if !ok { throw NSError(domain: message, code: 1) } }
func xml(_ s: String) -> String { s.replacingOccurrences(of: "&", with: "&amp;").replacingOccurrences(of: "<", with: "&lt;").replacingOccurrences(of: ">", with: "&gt;").replacingOccurrences(of: "\"", with: "&quot;") }
func color(_ hex: UInt32) -> CGColor { CGColor(red: CGFloat((hex >> 16) & 255)/255, green: CGFloat((hex >> 8) & 255)/255, blue: CGFloat(hex & 255)/255, alpha: 1) }
func line(_ s: String, _ size: CGFloat) -> CTLine {
 let font = NSFont(name: "PingFangSC-Semibold", size: size) ?? NSFont.systemFont(ofSize: size, weight: .semibold)
 return CTLineCreateWithAttributedString(NSAttributedString(string: s, attributes: [.font: font, .foregroundColor: NSColor(cgColor: color(0x504d48))!]))
}
do {
 try require(CommandLine.arguments.count == 3, "Usage: swift build.swift post.json NEW_OUTPUT_DIRECTORY")
 let input = URL(fileURLWithPath: CommandLine.arguments[1]), out = URL(fileURLWithPath: CommandLine.arguments[2])
 let root = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
 let post = try JSONDecoder().decode(Post.self, from: Data(contentsOf: input))
 try require(!post.title.isEmpty && post.title.count <= 20 && !post.title.contains("\n"), "Title must be one line, 1–20 characters")
 try require(!post.body.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty, "Candidate body is empty")
 try require(post.lines.count == 4 && post.lines.allSatisfy { !$0.isEmpty && !$0.contains("\n") }, "Cover needs four non-empty lines")
 try require(post.lines.last == "正在看机会", "Final cover line must be 正在看机会")
 let widths = post.lines.map { CTLineGetTypographicBounds(line($0, 150), nil, nil, nil) }
 try require(widths.allSatisfy { $0 <= 1060 }, "Cover text is too long: shorten wording, do not shrink the type")
 try require(CTLineGetTypographicBounds(line(post.subtitle, 34), nil, nil, nil) <= 1060 && !post.subtitle.contains("\n"), "Subtitle overflows")
 let fm = FileManager.default
 try require(!fm.fileExists(atPath: out.path), "Output already exists; choose a new directory to preserve existing work")
 let asset = try Data(contentsOf: root.appendingPathComponent("assets/recruiting-service.png"))
 let expected = try String(contentsOf: root.appendingPathComponent("assets/recruiting-service.sha256"), encoding: .utf8).trimmingCharacters(in: .whitespacesAndNewlines)
 let actual = SHA256.hash(data: asset).map { String(format: "%02x", $0) }.joined()
 try require(actual == expected, "Fixed service image hash mismatch; do not regenerate or silently accept a replacement")
 let about = try String(contentsOf: root.appendingPathComponent("references/about-me.md"), encoding: .utf8)
 try require(!post.body.contains("🌟关于我"), "body is candidate section only; fixed About section is appended automatically")
 let ctx = CGContext(data: nil, width: 1200, height: 1600, bitsPerComponent: 8, bytesPerRow: 4800, space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
 var svg = "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"1200\" height=\"1600\" viewBox=\"0 0 1200 1600\"><title>候选人推荐封面</title>"
 func rect(_ id: String, _ x: CGFloat, _ y: CGFloat, _ w: CGFloat, _ h: CGFloat, _ fill: UInt32) {
  ctx.setFillColor(color(fill)); ctx.fill(CGRect(x: x, y: 1600-y-h, width: w, height: h))
  svg += "<rect id=\"\(id)\" x=\"\(x)\" y=\"\(y)\" width=\"\(w)\" height=\"\(h)\" fill=\"#\(String(format: "%06x", fill))\"/>"
 }
 func text(_ id: String, _ s: String, _ x: CGFloat, _ y: CGFloat, _ size: CGFloat) {
  ctx.textPosition = CGPoint(x: x, y: 1600-y); CTLineDraw(line(s, size), ctx)
  svg += "<text id=\"\(id)\" x=\"\(x)\" y=\"\(y)\" font-family=\"PingFang SC,sans-serif\" font-size=\"\(size)\" font-weight=\"600\" fill=\"#504d48\">\(xml(s))</text>"
 }
 rect("Background",0,0,1200,1600,0xfffefa)
 // Decorative quotation marks, kept independent from the content.
 for x: CGFloat in [144,220] {
  ctx.setFillColor(color(0xf3ecdc));ctx.beginPath();ctx.move(to:CGPoint(x:x,y:1372));ctx.addLine(to:CGPoint(x:x,y:1417));ctx.addQuadCurve(to:CGPoint(x:x+53,y:1476),control:CGPoint(x:x,y:1466));ctx.addLine(to:CGPoint(x:x+57,y:1453));ctx.addQuadCurve(to:CGPoint(x:x+28,y:1425),control:CGPoint(x:x+29,y:1447));ctx.addLine(to:CGPoint(x:x+57,y:1425));ctx.addLine(to:CGPoint(x:x+57,y:1372));ctx.closePath();ctx.fillPath()
  svg += "<path d=\"M\(x) 228v-45q0-49 53-59l4 23q-28 6-29 28h29v53z\" fill=\"#f3ecdc\"/>"
 }
 for (i,s) in post.lines.enumerated() {
  let y = CGFloat(430+i*230)
  if i == 0 || i == 3 { rect("Highlight-\(i)",65,y-42,CGFloat(widths[i])+12,56,0xb0ff67) }
  text("Headline-\(i)",s,65,y,150)
 }
 text("Preferences",post.subtitle,70,1300,34)
 rect("Accent",976,1435,80,19,0xf3ecdc)
 svg += "</svg>"
 let bitmap = NSBitmapImageRep(cgImage: ctx.makeImage()!)
 let png = bitmap.representation(using: .png, properties: [:])!
 try fm.createDirectory(at: out, withIntermediateDirectories: true)
 try Data(svg.utf8).write(to: out.appendingPathComponent("01_候选人推荐封面.svg"), options: .atomic)
 try png.write(to: out.appendingPathComponent("01_候选人推荐封面.png"), options: .atomic)
 try asset.write(to: out.appendingPathComponent("02_招聘服务介绍.png"), options: .atomic)
 try Data((post.title+"\n\n"+post.body.trimmingCharacters(in: .whitespacesAndNewlines)+"\n\n"+about).utf8).write(to: out.appendingPathComponent("标题与正文.txt"), options: .atomic)
 print("Created SVG, PNG, unchanged service image and title/body. Title: \(post.title.count) characters. Service SHA256: \(actual)")
} catch { fputs("Error: \(error)\n", stderr); exit(1) }
