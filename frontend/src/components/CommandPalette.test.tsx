import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { CommandPalette, type Command } from './CommandPalette'

function setup() {
  const runs = { ny: vi.fn(), tema: vi.fn(), docs: vi.fn() }
  const commands: Command[] = [
    { id: 'ny', label: 'Ny konversation', hint: 'Ctrl K', run: runs.ny },
    { id: 'tema', label: 'Byt till ljust läge', run: runs.tema },
    { id: 'docs', label: 'Visa dokument', run: runs.docs },
  ]
  const onClose = vi.fn()
  render(<CommandPalette commands={commands} onClose={onClose} />)
  return { runs, onClose }
}

describe('CommandPalette', () => {
  it('starts focused in the search box and lists every command', () => {
    setup()

    expect(screen.getByRole('combobox')).toHaveFocus()
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(['Ny konversationCtrl K', 'Byt till ljust läge', 'Visa dokument'])
  })

  it('filters while typing (also with Swedish letters) and runs the chosen command with Enter', async () => {
    const { runs, onClose } = setup()

    await userEvent.type(screen.getByRole('combobox'), 'LJUST')
    expect(screen.getAllByRole('option')).toHaveLength(1)
    await userEvent.keyboard('{Enter}')

    expect(runs.tema).toHaveBeenCalledOnce()
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('moves with the arrow keys, wrapping around', async () => {
    const { runs } = setup()

    await userEvent.keyboard('{ArrowDown}{ArrowDown}{ArrowDown}{ArrowUp}{Enter}')

    expect(screen.getAllByRole('option')[2]).toBeInTheDocument()
    expect(runs.docs).toHaveBeenCalledOnce() // down x3 wraps to the first, up goes to the last
  })

  it('runs a command on click, and closes with Escape without running anything', async () => {
    const { runs, onClose } = setup()

    await userEvent.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalledOnce()
    expect(runs.ny).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole('option', { name: /Visa dokument/ }))
    expect(runs.docs).toHaveBeenCalledOnce()
  })

  it('says so when nothing matches and does nothing on Enter', async () => {
    const { onClose } = setup()

    await userEvent.type(screen.getByRole('combobox'), 'qqq{Enter}')

    expect(screen.getByText('Inget kommando matchar.')).toBeInTheDocument()
    expect(onClose).not.toHaveBeenCalled()
  })
})
