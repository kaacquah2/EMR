/**
 * Global configuration to override default Date.prototype localization methods.
 * Ensures the frontend displays dates and times in the "Africa/Accra" timezone
 * and uses "en-GH" locale formatting by default, avoiding hydration mismatches
 * between UTC server-side rendering and client-side formatting.
 */

const DEFAULT_LOCALE = "en-GH";
const DEFAULT_TIMEZONE = "Africa/Accra";

if (typeof Date !== "undefined") {
  const originalToLocaleString = Date.prototype.toLocaleString;
  Date.prototype.toLocaleString = function (
    locales?: string | string[],
    options?: Intl.DateTimeFormatOptions
  ) {
    const mergedOptions = { timeZone: DEFAULT_TIMEZONE, ...options };
    return originalToLocaleString.call(this, locales || DEFAULT_LOCALE, mergedOptions);
  };

  const originalToLocaleDateString = Date.prototype.toLocaleDateString;
  Date.prototype.toLocaleDateString = function (
    locales?: string | string[],
    options?: Intl.DateTimeFormatOptions
  ) {
    const mergedOptions = { timeZone: DEFAULT_TIMEZONE, ...options };
    return originalToLocaleDateString.call(this, locales || DEFAULT_LOCALE, mergedOptions);
  };

  const originalToLocaleTimeString = Date.prototype.toLocaleTimeString;
  Date.prototype.toLocaleTimeString = function (
    locales?: string | string[],
    options?: Intl.DateTimeFormatOptions
  ) {
    const mergedOptions = { timeZone: DEFAULT_TIMEZONE, ...options };
    return originalToLocaleTimeString.call(this, locales || DEFAULT_LOCALE, mergedOptions);
  };
}
