# Table Component Documentation

## Overview
A flexible, accessible, and reusable table component for MedSync frontend built with React, TypeScript, and Tailwind CSS. Provides semantic HTML table structure with support for sorting, striped rows, hover effects, and full dark mode support.

## Features Implemented

✅ **Table Composition (shadcn pattern)**
- `<Table>` - Root component with responsive wrapper
- `<TableCaption>` - Accessible table caption
- `<TableHeader>` - Semantic thead wrapper
- `<TableBody>` - Semantic tbody wrapper (with striping context support)
- `<TableBodyWithStriping>` - Helper component for automatic row indexing
- `<TableRow>` - Row component with striped/hover styling
- `<TableHead>` - Header cell with optional sorting
- `<TableCell>` - Body cell with alignment support

✅ **Sorting**
- `sortable` prop on TableHead enables sort mode
- `onSort` callback for sort handler
- `sortOrder` prop accepts 'asc' | 'desc' | 'none'
- Visual sort indicators (up/down/unsorted arrows)
- `aria-sort` attribute for accessibility

✅ **Visual Design**
- Striped rows (zebra pattern) - alternating row colors
- Hover effects on rows - highlight on mouse over
- Proper spacing and padding (consistent px-4 py-3)
- Subtle gray borders (gray-200 / dark:gray-700)
- Full dark mode support with dark: prefixes
- Typography: smaller font (text-sm), proper text colors

✅ **Accessibility**
- Semantic HTML (table, thead, tbody, th, td)
- `role="table"` on root
- `role="columnheader"` on header cells
- `aria-sort="ascending" | "descending" | "none"` for sortable headers
- `<TableCaption>` for table description
- Screen reader optimized

✅ **Responsive Design**
- Horizontal scroll wrapper for mobile overflow
- `overflow-x-auto` on desktop containers
- Proper text sizing that works on all screens

✅ **TypeScript**
- Full TypeScript strict mode (no any)
- Complete interface definitions for all components
- Proper generic types with forwardRef
- Type exports for consumer usage

✅ **Code Quality**
- Composition-based design (like shadcn)
- Forward refs on all visual components
- JSDoc comments on all components and interfaces
- displayName set for debugging
- Clean exports with type exports
- React Context for striping support (RowIndexContext)
- No unnecessary dependencies

## Usage Examples

### Basic Table
```tsx
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/Table';

export function BasicTable() {
  return (
    <Table striped>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Email</TableHead>
          <TableHead>Status</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.map((item) => (
          <TableRow key={item.id}>
            <TableCell>{item.name}</TableCell>
            <TableCell>{item.email}</TableCell>
            <TableCell>{item.status}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
```

### Table with Sorting
```tsx
import { useState } from 'react';
import {
  Table,
  TableCaption,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/Table';

export function SortableTable() {
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc' | 'none'>('none');

  const handleSort = () => {
    if (sortOrder === 'none') setSortOrder('asc');
    else if (sortOrder === 'asc') setSortOrder('desc');
    else setSortOrder('none');
  };

  return (
    <Table striped>
      <TableCaption>Patient List</TableCaption>
      <TableHeader>
        <TableRow>
          <TableHead
            sortable
            onSort={handleSort}
            sortOrder={sortOrder}
          >
            Patient Name
          </TableHead>
          <TableHead>Hospital</TableHead>
          <TableHead>Status</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.map((item) => (
          <TableRow key={item.id}>
            <TableCell>{item.name}</TableCell>
            <TableCell>{item.hospital}</TableCell>
            <TableCell>{item.status}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
```

### Table with Column Alignment
```tsx
<Table striped>
  <TableHeader>
    <TableRow>
      <TableHead align="left">Patient</TableHead>
      <TableHead align="center">Date</TableHead>
      <TableHead align="right">Amount</TableHead>
    </TableRow>
  </TableHeader>
  <TableBody>
    {data.map((item) => (
      <TableRow key={item.id}>
        <TableCell align="left">{item.patient}</TableCell>
        <TableCell align="center">{item.date}</TableCell>
        <TableCell align="right">${item.amount}</TableCell>
      </TableRow>
    ))}
  </TableBody>
</Table>
```

## Component API

### Table
Root table component with responsive wrapper.

**Props:**
- `children: React.ReactNode` - Table content (header, body)
- `className?: string` - Additional CSS classes
- `striped?: boolean` - Enable striped row styling (default: true)

### TableCaption
Accessible table caption for screen readers.

**Props:**
- `children: React.ReactNode` - Caption text
- `className?: string` - Additional CSS classes

### TableHeader
Semantic thead wrapper.

**Props:**
- `children: React.ReactNode` - Header rows
- `className?: string` - Additional CSS classes

### TableBody
Semantic tbody wrapper with optional row striping context.

**Props:**
- `children: React.ReactNode` - Body rows
- `className?: string` - Additional CSS classes

### TableBodyWithStriping
Helper tbody component that automatically tracks row indices for striping.

**Props:**
- `children: React.ReactNode` - Body rows
- `striped?: boolean` - Enable striping (default: true)
- `className?: string` - Additional CSS classes

### TableRow
Table row component with hover and striping support.

**Props:**
- `children: React.ReactNode` - Row cells
- `className?: string` - Additional CSS classes
- `index?: number` - Row index for striping (auto-provided by TableBodyWithStriping)

### TableHead
Header cell component with optional sorting.

**Props:**
- `children: React.ReactNode` - Header text
- `sortable?: boolean` - Enable sorting (default: false)
- `onSort?: () => void` - Callback when column header is clicked
- `sortOrder?: 'asc' | 'desc' | 'none'` - Current sort state (default: 'none')
- `align?: 'left' | 'center' | 'right'` - Text alignment (default: 'left')
- `className?: string` - Additional CSS classes

### TableCell
Body cell component with alignment support.

**Props:**
- `children: React.ReactNode` - Cell content
- `align?: 'left' | 'center' | 'right'` - Text alignment (default: 'left')
- `className?: string` - Additional CSS classes

## Styling Classes

### Color Palette
- Header background: `bg-gray-50 dark:bg-gray-900`
- Header border: `border-gray-200 dark:border-gray-700`
- Striped rows: `bg-gray-50 dark:bg-gray-800/50`
- Hover background: `hover:bg-gray-100 dark:hover:bg-gray-800`
- Text: `text-gray-700 dark:text-gray-300`
- Header text: `text-gray-900 dark:text-gray-100`

### Spacing
- Cell padding: `px-4 py-3`
- Border styling: `border-collapse`
- Table width: `w-full`

### Responsive
- Mobile: Horizontal scroll wrapper `overflow-x-auto`
- Maintains readability on small screens

## Accessibility Features

1. **Semantic HTML**: Uses proper table markup (table, thead, tbody, th, td)
2. **ARIA Attributes**:
   - `role="table"` on root element
   - `role="columnheader"` on header cells
   - `aria-sort="ascending" | "descending" | "none"` on sortable headers
3. **Table Caption**: `<TableCaption>` component for table description
4. **Screen Reader Support**: Proper semantic structure for assistive technologies
5. **Keyboard Navigation**: Clickable sort headers are keyboard accessible

## Dark Mode

All components include full dark mode support:
- Headers adapt to dark background
- Text colors adjust for contrast
- Borders use dark mode colors
- Hover states work in both light and dark modes

Example in Tailwind:
```tsx
className="bg-gray-50 dark:bg-gray-900"
```

## File Location
`medsync-frontend/src/components/ui/Table.tsx`

## Exports
- Components: `Table`, `TableCaption`, `TableHeader`, `TableBody`, `TableBodyWithStriping`, `TableRow`, `TableHead`, `TableCell`
- Types: `TableProps`, `TableHeadProps`, `TableCellProps`, `TableCaptionProps`, `TableSectionProps`, `TableRowProps`

## Integration with MedSync

The Table component is designed to replace raw HTML tables used throughout MedSync:
- Patient lists
- Lab orders
- Worklists
- Staff directories
- Any tabular data display

Example migration:
```tsx
// Before: Raw HTML
<table>
  <tr><td>Patient Name</td></tr>
</table>

// After: Table component
<Table striped>
  <TableHeader>
    <TableRow>
      <TableHead>Patient Name</TableHead>
    </TableRow>
  </TableHeader>
  <TableBody>
    {patients.map(p => <TableRow key={p.id}><TableCell>{p.name}</TableCell></TableRow>)}
  </TableBody>
</Table>
```

## Testing

The component includes a demo file (`Table.demo.tsx`) showing:
- Basic table structure
- Sortable columns
- Striped rows
- Hover effects
- Full TypeScript integration

All components use forward refs and are fully compatible with React 19 and Next.js 16.
