import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import LoginPage from './page';
import * as React from 'react';

// Mock the hooks
vi.mock('@/lib/auth-context', () => ({
  useAuth: () => ({
    login: vi.fn(),
  }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock('@/hooks/use-passkey', () => ({
  usePasskey: () => ({
    isSupported: true,
    isPlatformAvailable: true,
    authenticate: vi.fn(),
  }),
}));

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders sign in form by default', () => {
    render(<LoginPage />);
    expect(screen.getByRole('heading', { name: /sign in to medsync/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/^email$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument();
  });

  it('shows error on invalid credentials', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: async () => ({ message: 'Invalid credentials' }),
    });

    render(<LoginPage />);
    
    fireEvent.change(screen.getByLabelText(/^email$/i), { target: { value: 'test@example.com' } });
    fireEvent.change(screen.getByLabelText(/^password$/i), { target: { value: 'wrongpass' } });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Invalid credentials');
    });
  });

  it('switches to MFA step on successful credentials if required', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        mfa_required: true,
        mfa_token: 'test-token',
        mfa_channel: 'authenticator'
      }),
    });

    render(<LoginPage />);
    
    fireEvent.change(screen.getByLabelText(/^email$/i), { target: { value: 'test@example.com' } });
    fireEvent.change(screen.getByLabelText(/^password$/i), { target: { value: 'correctpass' } });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText(/enter your 6-digit code/i)).toBeInTheDocument();
    });
  });

  it('allows switching to backup code mode in MFA step', async () => {
    // First get to MFA step
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        mfa_required: true,
        mfa_token: 'test-token',
        mfa_channel: 'authenticator'
      }),
    });

    render(<LoginPage />);
    
    fireEvent.change(screen.getByLabelText(/^email$/i), { target: { value: 'test@example.com' } });
    fireEvent.change(screen.getByLabelText(/^password$/i), { target: { value: 'correctpass' } });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText(/use backup code/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText(/use backup code/i));
    
    expect(screen.getByLabelText(/backup code/i)).toBeInTheDocument();
    expect(screen.getByText(/use authenticator app instead/i)).toBeInTheDocument();
  });
});
