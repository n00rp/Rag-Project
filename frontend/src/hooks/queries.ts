import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import type { ChatAnswer, DocumentDto } from '../lib/types'

const POLL_MS = 1500

export function useDocuments() {
  return useQuery({
    queryKey: ['documents'],
    queryFn: api.listDocuments,
    // Poll only while something is still being processed in the background.
    refetchInterval: (query) =>
      query.state.data?.some((d) => d.status === 'Queued' || d.status === 'Processing')
        ? POLL_MS
        : false,
  })
}

export function useUploadDocument() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.uploadDocument,
    onSuccess: (doc) =>
      qc.setQueryData<DocumentDto[]>(['documents'], (old = []) => [doc, ...old]),
  })
}

export function useDeleteDocument() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.deleteDocument,
    onSuccess: (_void, id) =>
      qc.setQueryData<DocumentDto[]>(['documents'], (old = []) => old.filter((d) => d.id !== id)),
  })
}

export function useRetryDocument() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.retryDocument,
    onSuccess: (doc) =>
      qc.setQueryData<DocumentDto[]>(['documents'], (old = []) =>
        old.map((d) => (d.id === doc.id ? doc : d)),
      ),
  })
}

export function useHistory() {
  return useQuery({ queryKey: ['history'], queryFn: api.history })
}

export function useClearHistory() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.clearHistory,
    onSuccess: () => qc.setQueryData<ChatAnswer[]>(['history'], []),
  })
}

export function useAsk() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (question: string) => api.ask(question),
    onSuccess: (answer) =>
      qc.setQueryData<ChatAnswer[]>(['history'], (old = []) => [...old, answer]),
  })
}

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: api.health,
    refetchInterval: 15_000,
    retry: false,
  })
}
