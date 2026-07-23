import { useState, useEffect } from 'react';

/**
 * Custom debounce hook.
 * Delays updating the debounced value until `delay` ms after the last change.
 * Used in the Dashboard search bar to prevent API spam while typing.
 */
export function useDebounce(value, delay = 500) {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
}
