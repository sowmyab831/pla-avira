import { Component, ErrorInfo, ReactNode } from 'react'

interface Props { children: ReactNode }
interface State { error: Error | null }

/**
 * Page-level error boundary. A crash in one page renders a recovery card
 * instead of blanking the entire app. Keyed by currentPage in App.tsx so
 * navigating away resets the boundary automatically.
 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Page render failed:', error, info.componentStack)
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="max-w-lg mx-auto mt-16 p-6 rounded-2xl border border-red-200 bg-red-50 dark:bg-red-900/20 dark:border-red-800">
        <h2 className="text-lg font-semibold text-red-800 dark:text-red-200 mb-2">
          This section hit an error
        </h2>
        <p className="text-sm text-red-700 dark:text-red-300 mb-4 break-all">
          {String(this.state.error.message || this.state.error)}
        </p>
        <button
          onClick={() => { window.location.hash = 'dashboard'; this.setState({ error: null }) }}
          className="px-4 py-2 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700 transition-colors"
        >
          Back to Home
        </button>
      </div>
    )
  }
}
