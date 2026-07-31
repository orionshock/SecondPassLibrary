export type Location = {
  cfi: string
  locationLabel?: string
}

export type SessionProgress = {
  cfi: string
  locationLabel?: string
  updatedAt: string
}

export type HighlightColor =
  | "yellow"
  | "green"
  | "blue"
  | "pink"
  | "purple"
  | "orange"

export type Highlight = {
  clientAnnotationId: string
  kind: "highlight"
  location: Location
  body: {
    text: string
    prefix?: string
    suffix?: string
    color: HighlightColor
    note?: string
  }
  createdAt: string
  updatedAt: string
}

export type Bookmark = {
  clientAnnotationId: string
  kind: "bookmark"
  location: Location
  createdAt: string
  updatedAt: string
}

export type MarginaliaAnnotation = Highlight | Bookmark

export type ReadingSession = {
  sourceReadingSessionId: string
  name: string
  notes: string
  status: "active" | "closed"
  startedAt: string
  closedAt: string | null
  createdAt: string
  updatedAt: string
  progress: SessionProgress | null
  annotations: MarginaliaAnnotation[]
}

export type MarginaliaArchive = {
  type: "SecondPassMarginaliaExport"
  schemaVersion: "0.1.0"
  profile: "https://secondpasslibrary.local/specs/marginalia/0.1.0"
  generatedAt: string
  generator: string
  scope: { type: "all" | "selected" }
  books: Array<{
    fileHash: string
    title: string
    authors: string[]
    readingSessions: ReadingSession[]
  }>
}
