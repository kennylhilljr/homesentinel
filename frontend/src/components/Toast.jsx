import React, { useEffect } from 'react';

const ICONS = {
  success: '✓',
  error: '✗',
  info: 'i',
};

export function ToastContainer({ toasts, onDismiss }) {
  if (!toasts || toasts.length === 0) return null;
  return (
    <div className="hs-toast-container" role="region" aria-label="Notifications">
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

function ToastItem({ toast, onDismiss }) {
  useEffect(() => {
    if (toast.duration === 0) return undefined;
    const timeout = setTimeout(() => onDismiss(toast.id), toast.duration || 4500);
    return () => clearTimeout(timeout);
  }, [toast.id, toast.duration, onDismiss]);

  return (
    <div
      className={`hs-toast hs-toast-${toast.type || 'info'}`}
      role={toast.type === 'error' ? 'alert' : 'status'}
      aria-live={toast.type === 'error' ? 'assertive' : 'polite'}
    >
      <span className="hs-toast-icon" aria-hidden="true">{ICONS[toast.type] || ICONS.info}</span>
      <span className="hs-toast-message">{toast.message}</span>
      <button
        type="button"
        className="hs-toast-close"
        onClick={() => onDismiss(toast.id)}
        aria-label="Dismiss notification"
      >
        &times;
      </button>
    </div>
  );
}

export function useToasts() {
  const [toasts, setToasts] = React.useState([]);
  const push = React.useCallback((message, type = 'info', duration) => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, message, type, duration }]);
  }, []);
  const dismiss = React.useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);
  return { toasts, push, dismiss };
}
