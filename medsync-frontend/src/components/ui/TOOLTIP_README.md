# Tooltip Component Documentation

## Overview

The `Tooltip` component is a production-ready, accessible tooltip component built for MedSync with automatic positioning, smooth animations, and full keyboard support.

**Location:** `medsync-frontend/src/components/ui/Tooltip.tsx`

## Features

✅ **Automatic Positioning** - Detects viewport edges and repositions tooltip to stay visible
✅ **Accessible** - ARIA labels, keyboard support (ESC to dismiss), focus management
✅ **Multiple Triggers** - Hover (default), click, or focus-based tooltip display
✅ **Smooth Animations** - Fade-in/fade-out with configurable delays
✅ **Dark Mode Support** - Automatic theme adaptation via Tailwind's `dark:` prefix
✅ **Flexible Positioning** - Choose tooltip placement: top, bottom, left, right with auto-fallback
✅ **Portal Rendering** - Rendered outside DOM hierarchy to avoid z-index stacking issues
✅ **TypeScript Strict Mode** - Fully typed with no `any` types

## Installation

The component is already part of the MedSync frontend. Import it from:

```tsx
import { Tooltip } from '@/components/ui/Tooltip';
```

## Basic Usage

```tsx
<Tooltip content="Delete this record">
  <button>Delete</button>
</Tooltip>
```

## Component Props

### Required Props

| Prop | Type | Description |
|------|------|-------------|
| `children` | `React.ReactNode` | Content that triggers the tooltip (button, span, input, etc.) |
| `content` | `React.ReactNode` | Tooltip text or content to display |

### Optional Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `side` | `'top' \| 'bottom' \| 'left' \| 'right'` | `'top'` | Preferred position relative to trigger element |
| `trigger` | `'hover' \| 'click' \| 'focus'` | `'hover'` | How tooltip is triggered |
| `delayMs` | `number` | `200` | Delay in milliseconds before showing tooltip |
| `className` | `string` | `''` | Additional CSS classes for the tooltip box |

### Standard HTML Attributes

All standard HTML div attributes are supported via spread props:
- `data-*` attributes
- Custom event handlers
- `id`, `style`, etc.

## Usage Examples

### Example 1: Delete Button with Hover Tooltip

```tsx
<Tooltip content="Delete this record permanently" side="top" trigger="hover">
  <button className="px-4 py-2 bg-red-500 text-white rounded">
    Delete
  </button>
</Tooltip>
```

### Example 2: Information Icon with Click Tooltip

```tsx
<Tooltip content="This field is required" trigger="click" side="right">
  <span className="cursor-help text-gray-500">ℹ️</span>
</Tooltip>
```

### Example 3: Input with Focus Tooltip

```tsx
<Tooltip 
  content="Password must be 12+ characters with uppercase, lowercase, digit, and symbol"
  trigger="focus"
  side="right"
  delayMs={0}
>
  <input 
    type="password" 
    placeholder="Enter password"
    className="px-3 py-2 border rounded-lg"
  />
</Tooltip>
```

### Example 4: Custom Tooltip with Dark Mode

```tsx
<Tooltip
  content={
    <div className="font-semibold">
      <p>Copy to clipboard</p>
      <p className="text-xs opacity-75">Ctrl+C</p>
    </div>
  }
  side="bottom"
  className="max-w-sm"
>
  <button>Copy ID</button>
</Tooltip>
```

### Example 5: Delayed Tooltip (Reduce Flashing)

```tsx
<Tooltip 
  content="Processing..." 
  delayMs={500}
>
  <div className="animate-spin">⏳</div>
</Tooltip>
```

## Positioning Behavior

### Auto-Positioning Algorithm

The Tooltip automatically adjusts its position if it would be clipped by viewport edges:

1. **Preferred Side** - Initially attempts your specified side (top/bottom/left/right)
2. **Edge Detection** - Checks if tooltip fits within 8px margin from viewport edge
3. **Fallback Priority** - If preferred side doesn't fit, tries alternatives in this order:
   - Opposite side (top → bottom, left → right, etc.)
   - Adjacent sides (top/bottom → left/right)
4. **Final Clamping** - Clamps position to viewport with 8px margin

### Side Positions

```
        top
    ┌─────────┐
left │ Trigger │ right
    └─────────┘
      bottom
```

When you specify `side="top"`, the tooltip arrow points downward at the trigger.

## Trigger Modes

### Hover (Default)
Shows tooltip on mouse enter, hides on mouse leave. 200ms delay by default.

```tsx
<Tooltip content="Hover me" trigger="hover">
  <button>Hover</button>
</Tooltip>
```

### Click
Toggles tooltip visibility on click. Click again to dismiss. No auto-dismiss.

```tsx
<Tooltip content="Click to toggle" trigger="click">
  <button>Click</button>
</Tooltip>
```

**Note:** Clicking outside the tooltip does NOT close it. Users should click again or press ESC.

### Focus
Shows tooltip when trigger element receives focus, hides on blur.

```tsx
<Tooltip content="Focus help text" trigger="focus">
  <input placeholder="Focus me" />
</Tooltip>
```

## Accessibility Features

### ARIA Attributes

- **`role="tooltip"`** - Identifies element as tooltip for screen readers
- **`aria-describedby`** - Connects trigger to tooltip with unique ID
- Tooltip content is announced by screen readers

### Keyboard Support

- **ESC Key** - Dismisses tooltip when visible (all trigger modes)
- **Tab Navigation** - Works with focus trigger mode for form validation hints
- **Focus Management** - Tooltip doesn't steal focus from trigger

### Example: Accessible Form Validation

```tsx
<div className="space-y-3">
  <label htmlFor="email">Email</label>
  <Tooltip 
    content="Must be a valid email address (example@domain.com)" 
    trigger="focus"
    side="right"
  >
    <input 
      id="email"
      type="email"
      placeholder="Enter your email"
      required
      className="w-full px-3 py-2 border rounded-lg"
    />
  </Tooltip>
</div>
```

## Dark Mode Support

The Tooltip automatically adapts to light/dark mode:

- **Light Mode** - Dark gray background (`bg-slate-900`), white text
- **Dark Mode** - Light gray background (`dark:bg-slate-100`), dark text

No additional props needed—just ensure your app uses Tailwind's dark mode class toggle.

```tsx
// In your app's root or layout
<html className={darkMode ? 'dark' : ''}>
  {/* Tooltip will automatically use dark styles */}
  <Tooltip content="Theme-aware">
    <button>Content</button>
  </Tooltip>
</html>
```

## Styling & Customization

### Default Styles

```
Background:     Dark mode: bg-slate-900, Light mode: dark:bg-slate-100
Text Color:     White (dark) / Dark slate (light)
Border Radius:  rounded-md (6px)
Max Width:      max-w-xs (20rem / 320px)
Padding:        px-2.5 py-1.5
Font Size:      text-sm
Font Weight:    font-medium
Box Shadow:     shadow-lg
Z-Index:        z-50
```

### Custom Styling

Use the `className` prop to add additional styles:

```tsx
<Tooltip 
  content="Custom styled tooltip"
  className="max-w-sm bg-gradient-to-r from-blue-500 to-purple-600 text-white text-lg"
>
  <button>Styled</button>
</Tooltip>
```

**Note:** Custom classes are appended to the default classes. Use Tailwind's override syntax if needed:

```tsx
// Override max-width
<Tooltip content="..." className="!max-w-2xl">
  <button>Wide Tooltip</button>
</Tooltip>
```

## Common Patterns

### Help Icon with Tooltip

```tsx
import { HelpCircle } from 'lucide-react';

<div className="flex gap-2 items-center">
  <label>Admission Date</label>
  <Tooltip content="Date patient was admitted to hospital" side="right">
    <HelpCircle className="w-4 h-4 text-gray-500 cursor-help" />
  </Tooltip>
</div>
```

### Button with Complex Tooltip

```tsx
<Tooltip 
  content={
    <div>
      <p className="font-semibold mb-1">Before deleting:</p>
      <ul className="text-xs space-y-1">
        <li>• Record cannot be recovered</li>
        <li>• Audit log will show deletion</li>
        <li>• Associated data remains</li>
      </ul>
    </div>
  }
  side="left"
  delayMs={100}
>
  <button className="px-3 py-1 bg-red-600 text-white rounded-sm">
    Delete
  </button>
</Tooltip>
```

### Validation Feedback

```tsx
<Tooltip 
  content={error || "✓ Password is valid"}
  trigger="focus"
  side="right"
  className={error ? "!bg-red-600" : "!bg-green-600"}
>
  <input 
    type="password"
    value={password}
    onChange={(e) => setPassword(e.target.value)}
  />
</Tooltip>
```

## Performance Considerations

### Rendering

- **Portal-Based** - Tooltip renders outside component hierarchy via `React.createPortal`
- **Mounted Check** - Component ensures client-side mounting before rendering tooltip
- **No Re-render Bloat** - Trigger element wrapped in minimal div, tooltip only renders when visible

### Position Recalculation

Position is recalculated when:
- Tooltip becomes visible
- Window scrolls (capturing phase for child scrolls)
- Window is resized
- Side prop changes

Listeners are cleaned up when tooltip is hidden.

### Delayed Show

`delayMs` prop prevents tooltip spam during rapid mouse movement. Default 200ms is UX standard.

## Troubleshooting

### Tooltip Cut Off at Screen Edge

**Solution:** Component has built-in auto-positioning. If still cut off:
- Reduce tooltip width: `className="max-w-xs"` (default)
- Choose a different side prop initially
- Check for parent `overflow: hidden` CSS (tooltip uses portal to escape)

### Tooltip Not Appearing

**Checklist:**
- [ ] Is content prop set?
- [ ] For click trigger: did you click? Try ESC to close first
- [ ] For focus trigger: is the input actually focused?
- [ ] For hover trigger: are you hovering long enough (default 200ms)?
- [ ] Check z-index: tooltip uses `z-50`, ensure parent isn't higher
- [ ] Check browser DevTools: is element in DOM? Is it visible?

### Tooltip Position Wrong After Scroll

This shouldn't happen—position is recalculated on scroll. If it does:
- Parent element might have `position: relative` with `overflow: hidden`
- Portal is appended to `document.body`, so scroll inside a container may affect positioning
- Consider using `trigger="click"` where scroll is an issue

### Styling Issues in Dark Mode

Ensure your app properly toggles dark mode class:

```tsx
// ✅ Correct
<html className={isDark ? 'dark' : ''}>

// ❌ Wrong - dark mode class on body won't work for portal
<body className={isDark ? 'dark' : ''}>
```

Tooltip inherits dark mode from `<html>` element.

## Testing

### Manual Testing Checklist

- [ ] Hover trigger works with configurable delay
- [ ] Click trigger toggles on repeated clicks
- [ ] Focus trigger works with form inputs
- [ ] ESC key dismisses tooltip
- [ ] Tooltip stays within viewport edges
- [ ] Tooltip repositions when near screen edges
- [ ] Dark mode displays correct colors
- [ ] Multiple tooltips on same page work independently
- [ ] Custom className applies correctly
- [ ] Long content wraps properly
- [ ] Arrow points to correct trigger element

### Example Test Component

See `tooltip-demo.tsx` for a complete example component with all trigger modes and positioning options.

## Browser Support

- Chrome/Edge: ✅ Full support
- Firefox: ✅ Full support
- Safari: ✅ Full support
- IE 11: ❌ Not supported (uses modern React, Tailwind CSS 4)

## Dependencies

- React 19.2+
- React DOM 19.2+
- Tailwind CSS 4+
- TypeScript 5+ (for development)

The component uses only standard React APIs. No external UI libraries required.

## Related Components

- **Button** (`button.tsx`) - Common trigger element
- **Dialog** (`dialog.tsx`) - For modal tooltips/popovers
- **Badge** (`badge.tsx`) - Often paired with tooltips for status indicators
- **Skeleton** (`skeleton.tsx`) - Show while loading tooltip content

## Future Enhancements

Potential future improvements:
- Arrow customization (size, color, hidden)
- Content animation variants (fade, slide, scale)
- Pointer trap (keep tooltip visible on mouse enter)
- Async content loading with loading state
- Keyboard arrow navigation for multiple tooltips

## File Structure

```
medsync-frontend/
├── src/
│   └── components/
│       └── ui/
│           ├── Tooltip.tsx (Main component - 390 lines)
│           └── tooltip-demo.tsx (Example usage - 200 lines)
```

## API Reference

```typescript
interface TooltipProps {
  children: React.ReactNode;
  content: React.ReactNode;
  side?: 'top' | 'bottom' | 'left' | 'right';
  trigger?: 'hover' | 'click' | 'focus';
  className?: string;
  delayMs?: number;
}

type TooltipSide = 'top' | 'bottom' | 'left' | 'right';
type TooltipTrigger = 'hover' | 'click' | 'focus';
```

## License

Part of MedSync EMR system. See repository for license details.
