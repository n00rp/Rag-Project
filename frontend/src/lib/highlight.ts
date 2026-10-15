/**
 * Finds which text runs of a PDF page a cited excerpt covers, so the viewer can highlight them.
 *
 * The excerpt comes from the retrieval index and the page text from pdf.js, which split and hyphenate
 * text differently, so matching is done on runs of words, not characters. The excerpt may also start
 * with a document header that is not on this page (see ai-service `document_header`); those words
 * simply find no match.
 */

const WORDS_PER_GRAM = 4
/** A match further than this many words after the previous one is treated as a coincidence. */
const MAX_GAP = WORDS_PER_GRAM * 3
/** Fewer matching word runs than this is a coincidence, not the excerpt (excerpts are ~150 words). */
const MIN_MATCHES = 3

export function words(text: string): string[] {
  return text
    .normalize('NFKC')
    .toLowerCase()
    .split(/\s+/)
    .map((w) => w.replace(/[^\p{L}\p{N}]/gu, ''))
    .filter(Boolean)
}

/** Indexes (into `items`) of the text runs that overlap the excerpt; empty if it cannot be located. */
export function findHighlightedItems(items: string[], excerpt: string): Set<number> {
  const pageWords: string[] = []
  const itemOfWord: number[] = []
  items.forEach((item, i) => {
    for (const w of words(item)) {
      pageWords.push(w)
      itemOfWord.push(i)
    }
  })
  const excerptWords = words(excerpt)
  if (pageWords.length < WORDS_PER_GRAM || excerptWords.length < WORDS_PER_GRAM) return new Set()

  const gram = (list: string[], at: number) => list.slice(at, at + WORDS_PER_GRAM).join(' ')
  const positions = new Map<string, number[]>()
  for (let p = 0; p + WORDS_PER_GRAM <= pageWords.length; p++) {
    const key = gram(pageWords, p)
    positions.set(key, [...(positions.get(key) ?? []), p])
  }

  // Walk the excerpt in order and follow its matches forward through the page.
  let last = -1
  let first = -1
  let matches = 0
  for (let e = 0; e + WORDS_PER_GRAM <= excerptWords.length; e++) {
    const found = positions.get(gram(excerptWords, e))?.find((p) => p >= last)
    if (found === undefined || (last >= 0 && found - last > MAX_GAP)) continue
    if (first < 0) first = found
    last = found
    matches++
  }
  if (matches < MIN_MATCHES) return new Set()

  const covered = new Set<number>()
  for (let w = first; w < last + WORDS_PER_GRAM; w++) covered.add(itemOfWord[w])
  return covered
}
