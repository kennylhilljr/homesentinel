import React from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { vi } from 'vitest';
import ApiKeyPrompt from './ApiKeyPrompt';
import { AUTH_REQUIRED_EVENT, clearApiKey, getApiKey } from '../utils/apiAuth';

const requireAuth = (hadKey) => act(() => {
  window.dispatchEvent(new CustomEvent(AUTH_REQUIRED_EVENT, { detail: { hadKey } }));
});

describe('ApiKeyPrompt', () => {
  afterEach(() => clearApiKey());

  test('hidden until the API answers 401', () => {
    render(<ApiKeyPrompt onSaved={() => {}} />);
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  test('stores the entered key and calls onSaved', () => {
    const onSaved = vi.fn();
    render(<ApiKeyPrompt onSaved={onSaved} />);
    requireAuth(false);
    expect(screen.getByText(/requires an API key/)).toBeInTheDocument();
    const input = screen.getByLabelText(/requires an API key/);
    expect(input).toHaveAttribute('type', 'password');
    fireEvent.change(input, { target: { value: ' my-key ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(getApiKey()).toBe('my-key');
    expect(onSaved).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  test('says when the stored key was rejected and ignores empty input', () => {
    const onSaved = vi.fn();
    render(<ApiKeyPrompt onSaved={onSaved} />);
    requireAuth(true);
    expect(screen.getByText(/stored API key was rejected/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(onSaved).not.toHaveBeenCalled();
  });
});
