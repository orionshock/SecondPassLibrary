// Reading Session Annotation Profile TypeScript helpers
// Version: 0.1.0

export type EpubCfiSelector = {
  type: "FragmentSelector"
  conformsTo: "http://www.idpf.org/epub/linking/cfi/epub-cfi.html"
  value: `epubcfi(${string}`
  updated?: string
}

export type ReadingSessionStatus = "active" | "closed"

export type ReadingSession = {
  id: string
  type: "ReadingSession"
  sessionStatus: ReadingSessionStatus
  startedAt: string
  closedAt?: string
  currentLocation?: EpubCfiSelector
  layeredSession?: string[]
}

export type AnnotationMotivation = "highlighting" | "commenting" | "bookmarking"

export type TextualBodyPurpose =
  | "commenting"
  | "describing"
  | "highlighting"
  | "tagging"
  | "bookmarking"

export type TextualBody = {
  type: "TextualBody"
  purpose?: TextualBodyPurpose
  value?: string
  format?: string
  language?: string
}

export type AnnotationTarget = {
  source:
    | string
    | {
        id: string
        type?: "Text" | "Book"
      }
  selector: EpubCfiSelector
}

export type W3CReadingAnnotation = {
  id: string
  type: "Annotation"
  motivation: AnnotationMotivation | AnnotationMotivation[]
  created?: string
  modified?: string
  creator?: unknown
  body?: TextualBody | TextualBody[]
  target: AnnotationTarget
  sessionId?: string
  sourceSession?: string
  derivedFrom?: string
}

export type ExportBookMetadata = {
  id: string
  type?: "Book" | "Text"
  title?: string
  subtitle?: string
  author?: string[]
  publisher?: string
  publishedDate?: string
  language?: string
  isbn?: string
  fileHash: `sha256:${string}`
  epubUniqueIdentifier?: string
  epubMetadata?: Record<string, unknown>
  displayMetadata?: Record<string, unknown>
}

export type ReadingSessionAnnotationCollection = {
  "@context": unknown
  id: string
  type: "AnnotationCollection"
  profile: string
  schemaVersion: number
  label?: string
  generated: string
  generator: {
    type: "Software" | "SoftwareApplication"
    name: string
    version?: string
  }
  book: ExportBookMetadata
  session: ReadingSession
  total?: number
  items: W3CReadingAnnotation[]
}
