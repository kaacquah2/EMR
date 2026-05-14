'use client';

import React, { forwardRef } from 'react';

/**
 * Props for the Table root component
 */
interface TableProps {
  children: React.ReactNode;
  className?: string;
  striped?: boolean;
}

/**
 * Props for TableHeader, TableBody, and TableRow
 */
interface TableSectionProps {
  children: React.ReactNode;
  className?: string;
}

/**
 * Props for TableHead (header cell)
 */
interface TableHeadProps {
  children: React.ReactNode;
  sortable?: boolean;
  onSort?: () => void;
  sortOrder?: 'asc' | 'desc' | 'none';
  align?: 'left' | 'center' | 'right';
  className?: string;
}

/**
 * Props for TableCell (body cell)
 */
interface TableCellProps {
  children: React.ReactNode;
  align?: 'left' | 'center' | 'right';
  className?: string;
}

/**
 * Props for TableCaption
 */
interface TableCaptionProps {
  children: React.ReactNode;
  className?: string;
}

/**
 * Root Table component
 * Provides semantic HTML table structure with striped rows support
 */
const Table = forwardRef<HTMLTableElement, TableProps>(
  ({ children, className }, ref) => (
    <div className="w-full overflow-x-auto">
      <table
        ref={ref}
        className={`w-full border-collapse text-sm ${className || ''}`}
        role="table"
      >
        {children}
      </table>
    </div>
  )
);
Table.displayName = 'Table';

/**
 * TableCaption component for accessibility
 * Provides a description of the table content for screen readers
 */
const TableCaption = forwardRef<
  HTMLTableCaptionElement,
  TableCaptionProps
>(({ children, className }, ref) => (
  <caption
    ref={ref}
    className={`mb-4 text-sm text-gray-600 dark:text-gray-400 ${
      className || ''
    }`}
  >
    {children}
  </caption>
));
TableCaption.displayName = 'TableCaption';

/**
 * TableHeader component
 * Groups header rows together using semantic thead
 */
const TableHeader = forwardRef<HTMLTableSectionElement, TableSectionProps>(
  ({ children, className }, ref) => (
    <thead
      ref={ref}
      className={`border-b border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-900 ${
        className || ''
      }`}
    >
      {children}
    </thead>
  )
);
TableHeader.displayName = 'TableHeader';

/**
 * TableBody component
 * Groups body rows together using semantic tbody
 */
const TableBody = forwardRef<HTMLTableSectionElement, TableSectionProps>(
  ({ children, className }, ref) => (
    <tbody ref={ref} className={className || ''}>
      {children}
    </tbody>
  )
);
TableBody.displayName = 'TableBody';

/**
 * Context to track row index for striped styling
 */
const RowIndexContext = React.createContext<{
  rowIndex: number;
  striped: boolean;
} | null>(null);

/**
 * Hook to get row styling context
 */
const useRowContext = () => {
  const context = React.useContext(RowIndexContext);
  return context;
};

/**
 * TableRow component
 * Renders a table row with optional striped styling
 */
interface TableRowProps extends TableSectionProps {
  index?: number;
}

const TableRow = forwardRef<HTMLTableRowElement, TableRowProps>(
  ({ children, className, index = 0 }, ref) => {
    const context = useRowContext();
    const rowIndex = context?.rowIndex ?? index;
    const striped = context?.striped ?? false;

    const isEvenRow = rowIndex % 2 === 0;
    const stripedClass =
      striped && isEvenRow
        ? 'bg-gray-50 dark:bg-gray-800/50'
        : 'bg-white dark:bg-gray-950';

    return (
      <tr
        ref={ref}
        className={`border-b border-gray-200 transition-colors hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800 ${stripedClass} ${
          className || ''
        }`}
      >
        {children}
      </tr>
    );
  }
);
TableRow.displayName = 'TableRow';

/**
 * TableHead component
 * Renders header cells with optional sorting
 */
const TableHead = forwardRef<HTMLTableCellElement, TableHeadProps>(
  (
    {
      children,
      sortable = false,
      onSort,
      sortOrder = 'none',
      align = 'left',
      className,
    },
    ref
  ) => {
    const alignClasses = {
      left: 'text-left',
      center: 'text-center',
      right: 'text-right',
    };

    const handleClick = () => {
      if (sortable && onSort) {
        onSort();
      }
    };

    const isSortable = sortable && onSort;
    const ariaSortValue =
      sortOrder === 'asc'
        ? 'ascending'
        : sortOrder === 'desc'
          ? 'descending'
          : 'none';

    return (
      <th
        ref={ref}
        role="columnheader"
        aria-sort={isSortable ? ariaSortValue : undefined}
        onClick={handleClick}
        className={`
          px-4 py-3 font-semibold text-gray-900 dark:text-gray-100
          ${alignClasses[align]}
          ${isSortable ? 'cursor-pointer select-none hover:bg-gray-100 dark:hover:bg-gray-800' : ''}
          ${className || ''}
        `}
      >
        <div className="flex items-center gap-2">
          <span>{children}</span>
          {isSortable && (
            <SortIndicator sortOrder={sortOrder} />
          )}
        </div>
      </th>
    );
  }
);
TableHead.displayName = 'TableHead';

/**
 * TableCell component
 * Renders body cells with alignment support
 */
const TableCell = forwardRef<HTMLTableCellElement, TableCellProps>(
  ({ children, align = 'left', className }, ref) => {
    const alignClasses = {
      left: 'text-left',
      center: 'text-center',
      right: 'text-right',
    };

    return (
      <td
        ref={ref}
        className={`
          px-4 py-3 text-gray-700 dark:text-gray-300
          ${alignClasses[align]}
          ${className || ''}
        `}
      >
        {children}
      </td>
    );
  }
);
TableCell.displayName = 'TableCell';

/**
 * SortIndicator component
 * Visual indicator for sort state
 */
interface SortIndicatorProps {
  sortOrder: 'asc' | 'desc' | 'none';
}

const SortIndicator: React.FC<SortIndicatorProps> = ({ sortOrder }) => {
  if (sortOrder === 'none') {
    return (
      <svg
        className="h-4 w-4 text-gray-400 transition-transform"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M7 16V4m0 0L3 8m4-4l4 4M17 8v12m0 0l4-4m-4 4l-4-4"
        />
      </svg>
    );
  }

  if (sortOrder === 'asc') {
    return (
      <svg
        className="h-4 w-4 text-gray-600 dark:text-gray-400"
        fill="currentColor"
        viewBox="0 0 24 24"
      >
        <path d="M3 20h18v-2H3v2zM3 10h18V8H3v2zm9-9L1 9h16z" />
      </svg>
    );
  }

  return (
    <svg
      className="h-4 w-4 text-gray-600 dark:text-gray-400"
      fill="currentColor"
      viewBox="0 0 24 24"
    >
      <path d="M3 4h18v2H3V4zm0 10h18v-2H3v2zm9 9l8-8H4l8 8z" />
    </svg>
  );
};

/**
 * Wrapper component to provide striped row context
 * Use this when you need striped rows with automatic index tracking
 */
interface TableBodyWithStripingProps {
  children: React.ReactNode;
  striped?: boolean;
  className?: string;
}

const TableBodyWithStriping = forwardRef<
  HTMLTableSectionElement,
  TableBodyWithStripingProps
>(({ children, striped = true, className }, ref) => {
  const rows = React.Children.toArray(children);

  return (
    <tbody ref={ref} className={className || ''}>
      {rows.map((child, index) => {
        if (!React.isValidElement(child)) return child;

        return (
          <RowIndexContext.Provider
            key={index}
            value={{ rowIndex: index, striped }}
          >
            {React.cloneElement(child as React.ReactElement<{ index?: number }>, {
              index,
            })}
          </RowIndexContext.Provider>
        );
      })}
    </tbody>
  );
});
TableBodyWithStriping.displayName = 'TableBodyWithStriping';

export {
  Table,
  TableCaption,
  TableHeader,
  TableBody,
  TableBodyWithStriping,
  TableRow,
  TableHead,
  TableCell,
  type TableProps,
  type TableHeadProps,
  type TableCellProps,
  type TableCaptionProps,
  type TableSectionProps,
  type TableRowProps,
};
