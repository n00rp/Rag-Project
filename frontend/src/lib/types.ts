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
  /** The answer was cut off (stopped, or the model failed while writing it). */
  interrupted?: boolean
  /** The reader's verdict on the answer. */
  rating?: Rating | null
  /** How well the documents support the answer: the model said "delvis" when they only partly do. */
  support?: Support
  /** An overview question (summary, count, list): built from the best excerpts, so it may be incomplete. */
  broad?: boolean
  feedbackComment?: string | null
}

export type Rating = 'up' | 'down'
export type Support = 'fullt' | 'delvis'

export interface Health {
  database: boolean
  aiService: boolean
}

/** What the PDF viewer needs to open a document at a page. */
export interface ViewerTarget {
  documentId: string
  fileName: string
  page: number
  /** The cited excerpt; the viewer highlights it on the page when it can be located. */
  snippet?: string
}
