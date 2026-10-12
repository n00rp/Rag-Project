import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ToastProvider } from '../hooks/toast'
import { MAX_UPLOAD_BYTES } from '../lib/format'
import { UploadDropzone, validateFile } from './UploadDropzone'

afterEach(() => vi.unstubAllGlobals())

describe('validateFile', () => {
  it('accepts PDFs by type or extension', () => {
    expect(validateFile(new File(['x'], 'a.pdf', { type: 'application/pdf' }))).toBeNull()
    expect(validateFile(new File(['x'], 'B.PDF', { type: '' }))).toBeNull()
  })

  it('rejects other file types and oversized files with a readable reason', () => {
    expect(validateFile(new File(['x'], 'bild.png', { type: 'image/png' }))).toContain('inte en PDF')
    const big = new File(['x'], 'stor.pdf', { type: 'application/pdf' })
    Object.defineProperty(big, 'size', { value: MAX_UPLOAD_BYTES + 1 })
    expect(validateFile(big)).toContain('för stor')
  })
})

describe('UploadDropzone', () => {
  function renderDropzone() {
    return render(
      <QueryClientProvider client={new QueryClient()}>
        <ToastProvider>
          <UploadDropzone />
        </ToastProvider>
      </QueryClientProvider>,
    )
  }

  it('uploads a valid PDF and never sends an invalid file', async () => {
    const fetchMock = vi.fn(() => Promise.resolve(Response.json({ id: '1' }, { status: 202 })))
    vi.stubGlobal('fetch', fetchMock)
    renderDropzone()
    const input = screen.getByTestId('file-input')

    await userEvent.upload(input, new File(['%PDF-'], 'ok.pdf', { type: 'application/pdf' }), { applyAccept: false })
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))

    await userEvent.upload(input, new File(['x'], 'nej.txt', { type: 'text/plain' }), { applyAccept: false })
    expect(await screen.findByRole('alert')).toHaveTextContent('nej.txt är inte en PDF-fil')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
