import React from 'react';

const ICONS = {
  online: (
    <svg viewBox="0 0 12 12" width="10" height="10" aria-hidden="true" focusable="false">
      <circle cx="6" cy="6" r="3" fill="currentColor" />
    </svg>
  ),
  offline: (
    <svg viewBox="0 0 12 12" width="10" height="10" aria-hidden="true" focusable="false">
      <circle cx="6" cy="6" r="3" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <line x1="3" y1="3" x2="9" y2="9" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  ),
  warning: (
    <svg viewBox="0 0 12 12" width="10" height="10" aria-hidden="true" focusable="false">
      <path d="M6 1l5 9H1z" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <line x1="6" y1="5" x2="6" y2="7.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="6" cy="9" r="0.6" fill="currentColor" />
    </svg>
  ),
  new: (
    <svg viewBox="0 0 12 12" width="10" height="10" aria-hidden="true" focusable="false">
      <path d="M6 1.5l1.4 2.8 3.1.4-2.2 2.2.5 3.1L6 8.5 3.2 10l.5-3.1L1.5 4.7l3.1-.4z" fill="currentColor" />
    </svg>
  ),
};

const SR_LABELS = {
  online: 'Online',
  offline: 'Offline',
  warning: 'Warning',
  new: 'New',
};

export default function Badge({
  variant = 'default',
  icon,
  children,
  ariaLabel,
  className = '',
  ...rest
}) {
  const iconNode = icon === false ? null : (icon || ICONS[variant] || null);
  const label = ariaLabel || SR_LABELS[variant];
  return (
    <span
      className={`hs-badge hs-badge-${variant} ${className}`.trim()}
      role={ariaLabel ? 'img' : undefined}
      aria-label={ariaLabel}
      {...rest}
    >
      {iconNode && <span className="hs-badge-icon">{iconNode}</span>}
      <span className="hs-badge-text">{children}</span>
      {!ariaLabel && label && <span className="sr-only">{` (${label})`}</span>}
    </span>
  );
}
