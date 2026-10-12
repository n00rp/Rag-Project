export type DocumentStatus = 'Queued' | 'Processing' | 'Ready' | 'Failed'

export interface DocumentDto {
  id: string
  fileName: string
  sizeBytes: number
  status: DocumentStatus
  error: string | null
  pageCount: number | null
  chunkCount: number | null
  createdAt: string
}

export interface ChatSource {
  documentId: string
  fileName: string
  page: number
  snippet: string
  score: number
}

export interface ChatAnswer {
  id: string
  question: string
  answer: string
  grounded: boolean
  sources: ChatSource[]
  createdAt: string
}

export interface Health {
  database: boolean
  aiService: boolean
}

/** What the PDF viewer needs to open a document at a page. */
export interface ViewerTarget {
  documentId: string
  fileName: string
  page: number
}
