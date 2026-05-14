'use client';

import React, {
  useState,
  useRef,
  useEffect,
  useCallback,
  useMemo,
  useId,
} from 'react';
import { ChevronDown, X, Search } from 'lucide-react';

/**
 * Props interface for the SearchableSelect component
 * @template T The type of items in the options array
 */
export interface SearchableSelectProps<T> {
  /** Array of options to select from */
  options: T[];
  /** Currently selected value(s) */
  value?: T | T[];
  /** Callback when value changes */
  onChange: (value: T | T[]) => void;
  /** Enable multi-select mode */
  multi?: boolean;
  /** Show search input */
  searchable?: boolean;
  /** Show clear button */
  clearable?: boolean;
  /** Disable the component */
  disabled?: boolean;
  /** Placeholder text */
  placeholder?: string;
  /** Function to get display label for an option */
  getLabel?: (item: T) => string;
  /** Function to get unique identifier for an option */
  getValue?: (item: T) => string;
  /** Custom filter function */
  filterFn?: (item: T, searchTerm: string) => boolean;
  /** CSS class for the main container */
  className?: string;
  /** CSS class for the dropdown menu */
  menuClassName?: string;
}

/**
 * SearchableSelect component with search, keyboard navigation, and multi-select support
 *
 * @example
 * // Single select with search
 * <SearchableSelect
 *   options={icd10Codes}
 *   value={selectedCode}
 *   onChange={setSelectedCode}
 *   getLabel={(code) => `${code.id} - ${code.description}`}
 *   placeholder="Search ICD-10..."
 *   searchable
 * />
 *
 * @example
 * // Multi-select
 * <SearchableSelect
 *   options={roles}
 *   value={selectedRoles}
 *   onChange={setSelectedRoles}
 *   multi
 *   searchable
 *   placeholder="Select roles..."
 * />
 */
function SearchableSelect<T>({
  options,
  value,
  onChange,
  multi = false,
  searchable = true,
  clearable = true,
  disabled = false,
  placeholder = 'Select an option...',
  getLabel = (item) => String(item),
  getValue = (item) => String(item),
  filterFn,
  className = '',
  menuClassName = '',
}: SearchableSelectProps<T>): React.ReactElement {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [highlightedIndex, setHighlightedIndex] = useState(-1);

  const menuId = useId();

  const triggerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // Normalize value to array for easier handling
  const selectedValues = useMemo(() => {
    if (!value) return [];
    return Array.isArray(value) ? value : [value];
  }, [value]);

  // Filter options based on search term
  const filteredOptions = useMemo(() => {
    if (!searchable || !searchTerm) return options;

    const searchLower = searchTerm.toLowerCase();

    if (filterFn) {
      return options.filter((item) => filterFn(item, searchTerm));
    }

    return options.filter((item) => {
      const label = getLabel(item).toLowerCase();
      return label.includes(searchLower);
    });
  }, [options, searchTerm, searchable, getLabel, filterFn]);

  // Check if an option is selected
  const isOptionSelected = useCallback(
    (option: T) => {
      return selectedValues.some(
        (val) => getValue(val) === getValue(option)
      );
    },
    [selectedValues, getValue]
  );

  // Handle option selection
  const handleSelectOption = useCallback(
    (option: T) => {
      if (multi) {
        const isSelected = isOptionSelected(option);
        const newValue = isSelected
          ? selectedValues.filter(
              (val) => getValue(val) !== getValue(option)
            )
          : [...selectedValues, option];
        onChange(newValue);
      } else {
        onChange(option);
        setIsOpen(false);
        setSearchTerm('');
      }
      setHighlightedIndex(-1);
    },
    [multi, isOptionSelected, selectedValues, getValue, onChange]
  );

  // Handle clear all selections
  const handleClear = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      if (multi) {
        onChange([] as T[]);
      } else {
        onChange(undefined as unknown as T);
      }
      setSearchTerm('');
      inputRef.current?.focus();
    },
    [multi, onChange]
  );

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (!isOpen && e.key !== 'Enter' && e.key !== ' ') {
        if (searchable && (e.key.length === 1 || e.key === 'Backspace')) {
          setIsOpen(true);
        }
        return;
      }

      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          setIsOpen(true);
          setHighlightedIndex((prev) =>
            prev < filteredOptions.length - 1 ? prev + 1 : 0
          );
          break;

        case 'ArrowUp':
          e.preventDefault();
          setIsOpen(true);
          setHighlightedIndex((prev) =>
            prev > 0 ? prev - 1 : filteredOptions.length - 1
          );
          break;

        case 'Enter':
          e.preventDefault();
          if (isOpen && highlightedIndex >= 0) {
            handleSelectOption(filteredOptions[highlightedIndex]);
          }
          break;

        case 'Escape':
          e.preventDefault();
          setIsOpen(false);
          setHighlightedIndex(-1);
          break;

        case 'Backspace':
          if (clearable && !searchTerm && selectedValues.length > 0) {
            e.preventDefault();
            if (multi) {
              onChange(selectedValues.slice(0, -1) as T[]);
            } else {
              onChange(undefined as unknown as T);
            }
          }
          break;

        case ' ':
          if (!searchable) {
            e.preventDefault();
            setIsOpen(!isOpen);
          }
          break;

        default:
          break;
      }
    },
    [
      isOpen,
      searchable,
      filteredOptions,
      highlightedIndex,
      handleSelectOption,
      clearable,
      searchTerm,
      selectedValues,
      multi,
      onChange,
    ]
  );

  // Get display label for selected value(s)
  const getDisplayLabel = (): string => {
    if (selectedValues.length === 0) {
      return placeholder;
    }

    if (multi) {
      return selectedValues.length === 1
        ? getLabel(selectedValues[0])
        : `${selectedValues.length} items selected`;
    }

    return getLabel(selectedValues[0]);
  };

  // Handle outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        triggerRef.current &&
        !triggerRef.current.contains(event.target as Node) &&
        menuRef.current &&
        !menuRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => {
        document.removeEventListener('mousedown', handleClickOutside);
      };
    }
  }, [isOpen]);

  // Auto-focus search input when dropdown opens
  useEffect(() => {
    if (isOpen && searchable) {
      inputRef.current?.focus();
    }
  }, [isOpen, searchable]);

  return (
    <div
      className={`relative w-full ${className}`}
      ref={triggerRef}
    >
      {/* Trigger Button / Input */}
      <div
        className="relative"
        role="combobox"
        aria-expanded={isOpen}
        aria-owns={menuId}
        aria-controls={menuId}
      >
        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          disabled={disabled}
          className={`w-full px-3 py-2 text-left text-sm border rounded-md
            transition-colors duration-200 flex items-center justify-between gap-2
            ${
              disabled
                ? 'bg-gray-100 text-gray-500 cursor-not-allowed dark:bg-gray-800 dark:text-gray-500'
                : 'bg-white text-gray-900 border-gray-300 hover:border-gray-400 dark:bg-gray-950 dark:text-gray-50 dark:border-gray-700 dark:hover:border-gray-600'
            }
            ${isOpen ? 'ring-2 ring-blue-500 border-blue-500' : ''}
          `}
        >
          <div className="flex items-center gap-2 flex-1 min-w-0">
            {searchable && isOpen ? (
              <Search className="w-4 h-4 flex-shrink-0 text-gray-400" />
            ) : null}
            <input
              ref={inputRef}
              type="text"
              placeholder={getDisplayLabel()}
              value={searchable && isOpen ? searchTerm : ''}
              onChange={(e) => {
                if (searchable) {
                  setSearchTerm(e.target.value);
                  setHighlightedIndex(-1);
                }
              }}
              onKeyDown={handleKeyDown}
              onFocus={() => searchable && setIsOpen(true)}
              disabled={disabled}
              className={`flex-1 bg-transparent outline-none text-sm placeholder-gray-500
                dark:placeholder-gray-400
                ${!isOpen && !searchable ? 'cursor-pointer' : ''}
              `}
              role="textbox"
              aria-label={`${placeholder} search input`}
            />
            {!isOpen && selectedValues.length > 0 && !searchable ? (
              <span className="text-gray-700 dark:text-gray-300 truncate">
                {getDisplayLabel()}
              </span>
            ) : null}
          </div>

          <div className="flex items-center gap-1 flex-shrink-0">
            {clearable && selectedValues.length > 0 && !disabled ? (
              <button
                type="button"
                onClick={handleClear}
                className="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded transition-colors"
                aria-label="Clear selection"
              >
                <X className="w-4 h-4 text-gray-500 dark:text-gray-400" />
              </button>
            ) : null}
            <ChevronDown
              className={`w-4 h-4 text-gray-500 dark:text-gray-400 transition-transform duration-200 flex-shrink-0
                ${isOpen ? 'rotate-180' : ''}
              `}
            />
          </div>
        </button>

        {/* Multi-select selected items (badges) */}
        {multi && selectedValues.length > 0 && !isOpen ? (
          <div className="flex flex-wrap gap-1 mt-2">
            {selectedValues.map((item) => (
              <div
                key={getValue(item)}
                className="inline-flex items-center gap-1 px-2 py-1 bg-blue-100 text-blue-800
                  rounded text-xs dark:bg-blue-900 dark:text-blue-200"
              >
                <span>{getLabel(item)}</span>
                {clearable ? (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onChange(
                        selectedValues.filter(
                          (val) => getValue(val) !== getValue(item)
                        )
                      );
                    }}
                    className="ml-1 hover:text-blue-600 dark:hover:text-blue-300"
                    aria-label={`Remove ${getLabel(item)}`}
                  >
                    <X className="w-3 h-3" />
                  </button>
                ) : null}
              </div>
            ))}
          </div>
        ) : null}
      </div>

      {/* Dropdown Menu */}
      {isOpen ? (
        <div
          ref={menuRef}
          id={menuId}
          className={`absolute top-full left-0 right-0 mt-1 bg-white border border-gray-300
            rounded-md shadow-lg z-50 max-h-60 overflow-y-auto
            dark:bg-gray-950 dark:border-gray-700 ${menuClassName}`}
          role="listbox"
          aria-label={placeholder}
        >
          {filteredOptions.length === 0 ? (
            <div className="px-3 py-2 text-sm text-gray-500 dark:text-gray-400 text-center">
              No options found
            </div>
          ) : (
            filteredOptions.map((option, index) => {
              const isSelected = isOptionSelected(option);
              const isHighlighted = index === highlightedIndex;

              return (
                <div
                  key={getValue(option)}
                  role="option"
                  aria-selected={isSelected}
                  onClick={() => handleSelectOption(option)}
                  onMouseEnter={() => setHighlightedIndex(index)}
                  onMouseLeave={() => setHighlightedIndex(-1)}
                  className={`px-3 py-2 cursor-pointer text-sm transition-colors duration-150
                    flex items-center gap-2
                    ${
                      isHighlighted
                        ? 'bg-blue-50 dark:bg-blue-950'
                        : 'hover:bg-gray-100 dark:hover:bg-gray-900'
                    }
                    ${
                      isSelected
                        ? 'bg-blue-100 text-blue-900 dark:bg-blue-900 dark:text-blue-100'
                        : 'text-gray-900 dark:text-gray-50'
                    }
                  `}
                >
                  {multi ? (
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => {}}
                      className="cursor-pointer"
                      aria-label={getLabel(option)}
                    />
                  ) : (
                    <div
                      className={`w-4 h-4 rounded-full border-2 flex items-center justify-center
                        ${
                          isSelected
                            ? 'border-blue-500 bg-blue-500'
                            : 'border-gray-300 dark:border-gray-600'
                        }
                      `}
                    >
                      {isSelected ? (
                        <div className="w-2 h-2 bg-white rounded-full" />
                      ) : null}
                    </div>
                  )}
                  <span className="flex-1">{getLabel(option)}</span>
                </div>
              );
            })
          )}
        </div>
      ) : null}
    </div>
  );
}

export default SearchableSelect;
