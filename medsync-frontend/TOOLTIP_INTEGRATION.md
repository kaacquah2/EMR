/**
 * Quick Integration Guide for Tooltip Component
 * 
 * Place this file as reference: medsync-frontend/TOOLTIP_INTEGRATION.md
 */

# Tooltip Component - Quick Integration Guide

## 1. Basic Import

```tsx
import { Tooltip } from '@/components/ui/Tooltip';
```

## 2. Simplest Usage (Hover on Button)

```tsx
<Tooltip content="Delete this patient record">
  <button className="px-4 py-2 bg-red-500 text-white rounded">
    Delete Patient
  </button>
</Tooltip>
```

## 3. Common Use Cases

### Help Icon
```tsx
import { HelpCircle } from 'lucide-react';

<Tooltip content="Required field for patient identification" side="right">
  <HelpCircle className="w-4 h-4 text-gray-500 cursor-help" />
</Tooltip>
```

### Form Input Validation
```tsx
<Tooltip 
  content="Must be a valid Ghana Health Service ID format"
  trigger="focus"
  side="right"
>
  <input 
    type="text"
    placeholder="GHS ID"
    required
  />
</Tooltip>
```

### Action Button
```tsx
<Tooltip 
  content="Copy admission ID to clipboard"
  trigger="hover"
  side="top"
  delayMs={100}
>
  <button onClick={() => copyToClipboard(id)}>
    Copy ID
  </button>
</Tooltip>
```

### Information Alert
```tsx
<Tooltip 
  content={
    <div className="space-y-1">
      <p className="font-semibold">Emergency Contact Required</p>
      <p className="text-xs opacity-90">Must be a phone number in Ghana (+233)</p>
    </div>
  }
  trigger="click"
  side="bottom"
>
  <span className="text-amber-600 cursor-help">⚠️</span>
</Tooltip>
```

## 4. Available Props

| Prop | Type | Default | Example |
|------|------|---------|---------|
| `children` | ReactNode | - | `<button>Click me</button>` |
| `content` | ReactNode | - | `"Help text"` or `<div>Complex content</div>` |
| `side` | 'top'\|'bottom'\|'left'\|'right' | 'top' | `side="bottom"` |
| `trigger` | 'hover'\|'click'\|'focus' | 'hover' | `trigger="click"` |
| `className` | string | '' | `className="!max-w-sm"` |
| `delayMs` | number | 200 | `delayMs={0}` (instant) |

## 5. Positioning

The tooltip automatically repositions if it would be cut off:

```tsx
// If trigger is near top of screen, tooltip moves to bottom
<Tooltip side="top" content="I'll move to bottom if needed">
  <button>Hover me</button>
</Tooltip>
```

## 6. Trigger Modes

### Hover (Default)
Shows on mouse over with 200ms delay
```tsx
<Tooltip content="Information" trigger="hover">
  <button>Hover</button>
</Tooltip>
```

### Click
Toggle visibility by clicking
```tsx
<Tooltip content="Information" trigger="click">
  <button>Click</button>
</Tooltip>
```

### Focus
Show when input/button has keyboard focus
```tsx
<Tooltip content="Password requirements" trigger="focus">
  <input type="password" />
</Tooltip>
```

## 7. Styling

Default styling is dark tooltip with white text. Customize with:

```tsx
// More padding
<Tooltip 
  content="Styled tooltip"
  className="px-4 py-2"
>
  <button>Click</button>
</Tooltip>

// Custom colors (with override)
<Tooltip 
  content="Success!"
  className="!bg-green-600"
>
  <button>Done</button>
</Tooltip>

// Wider tooltip for long text
<Tooltip 
  content="This is a very long tooltip text that needs more space"
  className="!max-w-lg"
>
  <button>Info</button>
</Tooltip>
```

## 8. Dark Mode

The component automatically adapts to dark mode. No extra work needed:

```tsx
// Light mode: Dark gray bg, white text
// Dark mode: Light gray bg, dark text
<Tooltip content="Works in both themes">
  <button>Theme Aware</button>
</Tooltip>
```

## 9. Keyboard Support

- **ESC** - Close any visible tooltip
- **Tab** - Navigate to trigger with focus trigger mode
- **Mouse/Touch** - Works as expected

## 10. Accessibility

Tooltips include:
- ✅ `role="tooltip"` for screen readers
- ✅ `aria-describedby` to connect trigger and tooltip
- ✅ ESC key support
- ✅ Focus management
- ✅ Keyboard navigation support

## 11. Real-World Examples

### Patient Search with Helper
```tsx
<div className="flex gap-2">
  <input 
    type="search"
    placeholder="Search patients..."
  />
  <Tooltip 
    content="Search by name, ID, or phone number" 
    side="right"
    trigger="focus"
  >
    <button className="px-3 py-2 bg-teal-600 text-white rounded">
      Search
    </button>
  </Tooltip>
</div>
```

### Admin Action with Confirmation
```tsx
<Tooltip 
  content={
    <div>
      <p className="font-bold mb-1">Disable user account?</p>
      <p className="text-xs mb-2">User cannot log in. Data is preserved.</p>
      <p className="text-xs">Click to proceed</p>
    </div>
  }
  trigger="click"
  side="left"
>
  <button className="px-3 py-1 bg-red-600 text-white rounded-sm">
    Disable
  </button>
</Tooltip>
```

### Status Badge Info
```tsx
import { AlertCircle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

<Tooltip 
  content="Appointment pending patient confirmation (expires in 2 hours)"
  side="top"
>
  <div className="flex gap-2 items-center">
    <Badge variant="pending">PENDING</Badge>
    <AlertCircle className="w-4 h-4 text-amber-600" />
  </div>
</Tooltip>
```

## 12. Troubleshooting

### Tooltip doesn't appear
- For **hover**: Wait 200ms or set `delayMs={0}`
- For **click**: Click the trigger element
- For **focus**: Focus the input (click or Tab)

### Tooltip cut off at edge
- Tooltip auto-repositions, but if still cut off:
  - Reduce width: `className="!max-w-xs"`
  - Choose different side: `side="right"`

### Wrong position
- Check if parent has `overflow: hidden`
- Portal renders to `document.body`, not parent

## 13. Testing the Component

See `src/components/ui/tooltip-demo.tsx` for a full demo with:
- All trigger modes
- All positions
- Dark mode
- Accessibility features
- Multiple examples

## 14. Performance Notes

- Portal-based (efficient DOM placement)
- Lazy position calculation (only when visible)
- Minimal re-renders
- No external dependencies

## 15. Next Steps

1. Import Tooltip in your component
2. Wrap trigger element with Tooltip
3. Add content prop with help text
4. Choose trigger mode (hover/click/focus)
5. Done! ESC support and accessibility included

## 16. Documentation

Full documentation: `src/components/ui/TOOLTIP_README.md`

Need help? Check the README for:
- Detailed API reference
- All features explained
- Common patterns
- Accessibility deep dive
- Browser support
- File structure
