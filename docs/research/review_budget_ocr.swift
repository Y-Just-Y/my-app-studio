// Optional macOS-only review helper. OCR candidates are not verified budget facts.
import Foundation
import AppKit
import PDFKit
import Vision
import Darwin

struct Candidate: Codable { let text: String; let confidence: Float }
struct Line: Codable {
    let text: String
    let confidence: Float
    let box: [Double]
    let candidates: [Candidate]
}
struct PageResult: Codable {
    let pdfPage: Int
    let pixelWidth: Int
    let pixelHeight: Int
    let coordinates: String
    let lines: [Line]
}
let arguments = CommandLine.arguments
guard arguments.count == 5,
      let document = PDFDocument(url: URL(fileURLWithPath: arguments[1])),
      let first = Int(arguments[3]), let last = Int(arguments[4]),
      first >= 1, last >= first, last <= document.pageCount, last - first < 25 else {
    fatalError("Expected PDF, output directory and a valid range of at most 25 pages")
}
let directory = URL(fileURLWithPath: arguments[2], isDirectory: true)
try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
let encoder = JSONEncoder()
encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
for number in first...min(last, document.pageCount) {
    try autoreleasepool {
        guard let page = document.page(at: number - 1) else { return }
        let rectangle = page.bounds(for: .mediaBox)
        let scale = 2200.0 / max(rectangle.width, rectangle.height)
        let image = page.thumbnail(of: NSSize(width: rectangle.width * scale, height: rectangle.height * scale), for: .mediaBox)
        guard let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
            fatalError("Could not render PDF page")
        }
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.recognitionLanguages = ["en-US"]
        request.usesLanguageCorrection = false
        let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
        try handler.perform([request])
        let lines = (request.results ?? []).compactMap { observation -> Line? in
            let candidates = observation.topCandidates(3).map { Candidate(text: $0.string, confidence: $0.confidence) }
            guard let best = candidates.first else { return nil }
            let box = observation.boundingBox
            return Line(text: best.text, confidence: best.confidence,
                        box: [box.origin.x, box.origin.y, box.width, box.height], candidates: candidates)
        }
        let result = PageResult(pdfPage: number, pixelWidth: cgImage.width, pixelHeight: cgImage.height,
                                coordinates: "normalized image coordinates, origin bottom-left", lines: lines)
        try encoder.encode(result).write(to: directory.appendingPathComponent(String(format: "page-%03d.json", number)))
        print("OCR PDF page \(number): \(lines.count) observations")
        fflush(stdout)
    }
}
