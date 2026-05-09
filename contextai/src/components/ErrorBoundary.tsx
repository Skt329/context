import { Component, type ReactNode } from 'react';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

/**
 * React Error Boundary — catches render errors and displays a fallback UI
 * instead of crashing the entire application.
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[ContextAI] Component error:', error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback || (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              padding: '2rem',
              textAlign: 'center',
              gap: '1rem',
              color: 'var(--text-secondary, #999)',
            }}
          >
            <div style={{ fontSize: '2rem' }}>⚠️</div>
            <h3 style={{ margin: 0, color: 'var(--text-primary, #fff)' }}>
              Something went wrong
            </h3>
            <p style={{ margin: 0, fontSize: '0.875rem', maxWidth: '400px' }}>
              {this.state.error?.message || 'An unexpected error occurred.'}
            </p>
            <button
              onClick={() => this.setState({ hasError: false, error: null })}
              style={{
                padding: '0.5rem 1.5rem',
                borderRadius: '8px',
                border: '1px solid var(--border-primary, #333)',
                background: 'var(--bg-secondary, #1a1a1a)',
                color: 'var(--text-primary, #fff)',
                cursor: 'pointer',
                fontSize: '0.875rem',
              }}
            >
              Try Again
            </button>
          </div>
        )
      );
    }
    return this.props.children;
  }
}
