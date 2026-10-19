import { lazy, Suspense, type ComponentProps } from 'react'

// The Markdown libraries are a large part of the app and not needed for the first paint: until they have
// loaded (usually a moment) the answer is shown as plain text, then it is replaced by the formatted one.
const AnswerContent = lazy(() => import('./AnswerContent').then((m) => ({ default: m.AnswerContent })))

export function Answer(props: ComponentProps<typeof AnswerContent>) {
  return (
    <Suspense fallback={<div className="prose-answer whitespace-pre-wrap">{props.text}</div>}>
      <AnswerContent {...props} />
    </Suspense>
  )
}
