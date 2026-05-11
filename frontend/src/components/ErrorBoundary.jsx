// 2026-03-12: Global error boundary — catches render errors and shows
// a friendly fallback UI instead of a white screen.
// 2026-05-07: Token-driven CSS so the fallback adapts to active theme.
import React from 'react';
import './ErrorBoundary.css';

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
        <div className="error-boundary" role="alert" aria-live="assertive">
          <h1>Something went wrong</h1>
          <p className="error-boundary-desc">
            HomeSentinel encountered an unexpected error. Try reloading the page.
          </p>
          <button
            type="button"
            className="error-boundary-button"
            onClick={this.handleReload}
          >
            Reload
          </button>
          {this.state.error && (
            <pre className="error-boundary-trace">
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
