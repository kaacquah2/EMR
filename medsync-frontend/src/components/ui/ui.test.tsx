import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Button } from './button';
import { Input } from './input';
import { Card, CardTitle, CardContent } from './card';
import { Toast } from './toast';
import { Checkbox } from './Checkbox';
import * as React from 'react';

describe('Button component', () => {
  it('renders with children', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByText('Click me')).toBeInTheDocument();
  });

  it('handles click events', () => {
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Click me</Button>);
    fireEvent.click(screen.getByText('Click me'));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('is disabled when loading', () => {
    render(<Button loading>Click me</Button>);
    const button = screen.getByRole('button');
    expect(button).toBeDisabled();
    expect(screen.queryByText('Click me')).toBeInTheDocument();
  });

  it('applies variant classes', () => {
    const { rerender } = render(<Button variant="danger">Danger</Button>);
    expect(screen.getByRole('button')).toHaveClass('bg-[var(--red-600)]');
    
    rerender(<Button variant="outline">Outline</Button>);
    expect(screen.getByRole('button')).toHaveClass('border-[1.5px]');
  });
});

describe('Input component', () => {
  it('renders with label and placeholder', () => {
    render(<Input label="Email" placeholder="Enter email" />);
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Enter email')).toBeInTheDocument();
  });

  it('shows error message when provided', () => {
    render(<Input label="Email" error="Invalid email" />);
    expect(screen.getByText('Invalid email')).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toHaveAttribute('aria-invalid', 'true');
  });

  it('toggles password visibility', () => {
    render(<Input type="password" label="Password" />);
    const input = screen.getByLabelText(/^password$/i);
    const toggle = screen.getByLabelText(/show password/i);
    
    expect(input).toHaveAttribute('type', 'password');
    
    fireEvent.click(toggle);
    expect(input).toHaveAttribute('type', 'text');
    expect(screen.getByLabelText(/hide password/i)).toBeInTheDocument();
  });
});

describe('Card component', () => {
  it('renders title and content', () => {
    render(
      <Card>
        <CardTitle>User Profile</CardTitle>
        <CardContent>Details here</CardContent>
      </Card>
    );
    expect(screen.getByText('User Profile')).toBeInTheDocument();
    expect(screen.getByText('Details here')).toBeInTheDocument();
  });

  it('applies accent border', () => {
    const { container } = render(<Card accent="teal">Content</Card>);
    expect(container.firstChild).toHaveClass('border-l-[var(--teal-500)]');
  });
});

describe('Toast component', () => {
  it('renders message and calls onDismiss', () => {
    const handleDismiss = vi.fn();
    render(<Toast message="Success!" variant="success" onDismiss={handleDismiss} />);
    
    expect(screen.getByText('Success!')).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText(/dismiss/i));
    expect(handleDismiss).toHaveBeenCalledTimes(1);
  });
});

describe('Checkbox component', () => {
  it('renders with label and toggles', () => {
    render(<Checkbox label="Accept terms" />);
    const checkbox = screen.getByLabelText(/accept terms/i);
    expect(checkbox).toBeInTheDocument();
    expect(checkbox).not.toBeChecked();
    
    fireEvent.click(checkbox);
    expect(checkbox).toBeChecked();
  });
});
