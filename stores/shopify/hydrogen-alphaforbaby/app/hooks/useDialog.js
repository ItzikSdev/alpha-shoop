import {useCallback, useState} from 'react';

/**
 * Open/close state for a @material-tailwind/react <Dialog>. `handler` is the
 * no-arg toggle Dialog itself calls on backdrop click / Escape.
 */
export function useDialog(initialOpen = false) {
  const [open, setOpen] = useState(initialOpen);
  const openDialog = useCallback(() => setOpen(true), []);
  const closeDialog = useCallback(() => setOpen(false), []);
  const toggleDialog = useCallback(() => setOpen((o) => !o), []);
  return {open, openDialog, closeDialog, toggleDialog, handler: toggleDialog};
}
