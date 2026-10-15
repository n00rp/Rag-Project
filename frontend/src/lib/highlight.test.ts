import { describe, expect, it } from 'vitest'
import { findHighlightedItems, words } from './highlight'

const page = [
  'Protokoll nr 8',
  '§ 317 Ärendenummer SLK-2025-00392',
  'Yrkande från KD, M, D och L angående revidering',
  'av riktlinjen för finansverksamheten',
  'Beslut',
  'Yrkandet från KD, M, D och L avslås.',
  'Hampus Magnusson (M) deltar inte i handläggningen',
]

describe('words', () => {
  it('lower-cases, drops punctuation and keeps Swedish letters', () => {
    expect(words('Ärendenummer: SLK-2025-00392, åäö!')).toEqual(['ärendenummer', 'slk202500392', 'åäö'])
  })
})

describe('findHighlightedItems', () => {
  it('highlights the runs the excerpt covers', () => {
    const excerpt = 'Yrkande från KD, M, D och L angående revidering av riktlinjen för finansverksamheten Beslut'
    expect([...findHighlightedItems(page, excerpt)].sort()).toEqual([2, 3, 4])
  })

  it('ignores a document header that is not on the page', () => {
    const excerpt =
      'Protokoll nr 22 Sammanträdesdatum: 2025-11-26 Kommunstyrelsen. Hampus Magnusson (M) deltar inte i handläggningen'
    expect([...findHighlightedItems(page, excerpt)]).toEqual([6])
  })

  it('does not highlight when only a stray phrase matches', () => {
    expect(findHighlightedItems(page, 'Yrkande från KD, M, D men något helt annat står här')).toEqual(new Set())
  })

  it('returns nothing for text that is not on the page or too short to match', () => {
    expect(findHighlightedItems(page, 'ingenting av detta finns på sidan alls här')).toEqual(new Set())
    expect(findHighlightedItems(page, 'Beslut')).toEqual(new Set())
    expect(findHighlightedItems([], 'Beslut igen och igen och igen')).toEqual(new Set())
  })
})
