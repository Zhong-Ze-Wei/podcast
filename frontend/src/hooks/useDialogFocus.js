import { useEffect, useRef } from 'react';

export default function useDialogFocus(ref, enabled, onClose) {
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    if (!enabled) return;
    const previous = document.activeElement;
    const buttons = () => [...ref.current.querySelectorAll('button:not([disabled]), a[href], input, select, [tabindex="0"]')];
    buttons()[0]?.focus();
    const onKey = event => {
      if (event.key === 'Escape') close.current();
      if (event.key !== 'Tab') return;
      const elements = buttons();
      if (event.shiftKey && document.activeElement === elements[0]) { event.preventDefault(); elements.at(-1)?.focus(); }
      else if (!event.shiftKey && document.activeElement === elements.at(-1)) { event.preventDefault(); elements[0]?.focus(); }
    };
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('keydown', onKey); previous?.focus(); };
  }, [ref, enabled]);
}
