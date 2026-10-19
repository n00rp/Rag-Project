import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { SupportNotice } from './SupportNotice'

describe('SupportNotice', () => {
  it('says nothing about an ordinary, fully supported answer', () => {
    const { container } = render(<SupportNotice support="fullt" />)

    expect(container).toBeEmptyDOMElement()
  })

  it('warns when the documents only partly support the answer', () => {
    render(<SupportNotice support="delvis" />)

    expect(screen.getByText('Delvis stöd i dokumenten')).toBeInTheDocument()
  })

  it('warns that an overview may be incomplete, and can show both notices', () => {
    render(<SupportNotice support="delvis" broad />)

    expect(screen.getByText(/Översikt av de mest relevanta utdragen/)).toBeInTheDocument()
    expect(screen.getByText('Delvis stöd i dokumenten')).toBeInTheDocument()
  })
})
