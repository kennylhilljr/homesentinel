// Shown when the backend answers 401: asks for the HomeSentinel API key and stores it
// in this browser (see utils/apiAuth.js). Never shown when auth is off.
import React, { useEffect, useState } from 'react';
import { AUTH_REQUIRED_EVENT, setApiKey } from '../utils/apiAuth';

export default function ApiKeyPrompt({ onSaved = () => window.location.reload() }) {
  const [state, setState] = useState(null); // null | { hadKey }
  const [value, setValue] = useState('');

  useEffect(() => {
    const onAuthRequired = (event) => setState({ hadKey: Boolean(event.detail && event.detail.hadKey) });
    window.addEventListener(AUTH_REQUIRED_EVENT, onAuthRequired);
    return () => window.removeEventListener(AUTH_REQUIRED_EVENT, onAuthRequired);
  }, []);

  if (!state) return null;

  const submit = (event) => {
    event.preventDefault();
    if (!value.trim()) return;
    setApiKey(value);
    setValue('');
    setState(null);
    onSaved();
  };

  return (
    <div className="app-banner app-banner-error" role="dialog" aria-label="API key required">
      <form onSubmit={submit}>
        <label htmlFor="hs-api-key">
          {state.hadKey
            ? 'The stored API key was rejected. Enter the HomeSentinel API key:'
            : 'This HomeSentinel server requires an API key:'}
        </label>{' '}
        <input
          id="hs-api-key"
          type="password"
          autoComplete="current-password"
          value={value}
          onChange={(event) => setValue(event.target.value)}
        />{' '}
        <button type="submit">Save</button>
      </form>
    </div>
  );
}
