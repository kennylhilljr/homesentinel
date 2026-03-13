// 2026-03-12: Global error boundary — catches render errors and shows
// a friendly fallback UI instead of a white screen.
import React from 'react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('[ErrorBoundary] Uncaught render error:', error, errorInfo);
  }

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '100vh',
            padding: '2rem',
            fontFamily: "'Manrope', sans-serif",
            backgroundColor: '#0f172a',
            color: '#e2e8f0',
            textAlign: 'center',
          }}
        >
          <h1 style={{ fontSize: '1.5rem', marginBottom: '0.75rem' }}>
            Something went wrong
          </h1>
          <p style={{ color: '#94a3b8', marginBottom: '1.5rem', maxWidth: '400px' }}>
            HomeSentinel encountered an unexpected error. Try reloading the page.
          </p>
          <button
            onClick={this.handleReload}
            style={{
              padding: '0.6rem 1.5rem',
              fontSize: '0.95rem',
              fontWeight: 600,
              color: '#fff',
              backgroundColor: '#3b82f6',
              border: 'none',
              borderRadius: '8px',
              cursor: 'pointer',
            }}
          >
            Reload
          </button>
          {this.state.error && (
            <pre
              style={{
                marginTop: '2rem',
                padding: '1rem',
                backgroundColor: '#1e293b',
                borderRadius: '8px',
                fontSize: '0.75rem',
                color: '#f87171',
                maxWidth: '600px',
                overflow: 'auto',
                textAlign: 'left',
              }}
            >
              {this.state.error.toString()}
            </pre>
          )}
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
