export type Location = {
  cfi: string
  locationLabel?: string
}

export type SessionProgress = {
  location: Location
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
  id?: string
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
  id?: string
  kind: "bookmark"
  location: Location
  createdAt: string
  updatedAt: string
}

export type MarginaliaAnnotation = Highlight | Bookmark

export type ReadingSession = {
  id: string
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
