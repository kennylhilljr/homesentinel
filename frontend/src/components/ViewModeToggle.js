import React from 'react';
import './ViewModeToggle.css';

function ViewModeToggle({
  value,
  onChange,
  label = 'View',
  options = [
    { value: 'grid', label: 'Tiles' },
    { value: 'list', label: 'List' },
  ],
}) {
  return (
    <div className="view-mode-toggle" aria-label={label}>
      {label && <span className="view-mode-label">{label}</span>}
      <div className="view-mode-segment" role="tablist">
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            role="tab"
            aria-selected={value === option.value}
            className={`view-mode-button ${value === option.value ? 'active' : ''}`}
            onClick={() => onChange(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export default ViewModeToggle;
