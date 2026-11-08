"use client";

import { Children, createContext, isValidElement, useCallback, useContext, useEffect, useId, useRef, useState } from "react";
import type { DetailsHTMLAttributes, ReactNode } from "react";
import { createPortal } from "react-dom";

type InspectorState = {
  selected: string | null;
  container: HTMLDivElement | null;
  select: (id: string, trigger: HTMLElement) => void;
  clear: (id: string) => void;
};
const InspectorContext = createContext<InspectorState | null>(null);
const InsideInspector = createContext(false);

export function WorkspaceInspector({ enabled, scope, onOpenChange, children }: {
  enabled: boolean; scope: number; onOpenChange: (open: boolean) => void; children: ReactNode;
}) {
  const [selection, setSelection] = useState<{ id: string; scope: number } | null>(null);
  const [container, setContainer] = useState<HTMLDivElement | null>(null);
  const trigger = useRef<HTMLElement | null>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  // Discard a disclosure when leaving its chapter; returning must not reopen it.
  if (selection && selection.scope !== scope) setSelection(null);
  const selected = enabled && selection?.scope === scope ? selection.id : null;
  const select = useCallback((id: string, element: HTMLElement) => {
    trigger.current = element;
    setSelection({ id, scope });
  }, [scope]);
  const clear = useCallback((id: string) => setSelection(current => current?.id === id ? null : current), []);

  function restoreTrigger() {
    requestAnimationFrame(() => {
      if (trigger.current?.isConnected && trigger.current.getClientRects().length) trigger.current.focus({ preventScroll: true });
    });
  }

  function close() {
    setSelection(null);
    restoreTrigger();
  }
  useEffect(() => { onOpenChange(selected !== null); }, [selected, onOpenChange]);
  useEffect(() => {
    if (!selected) return;
    container?.scrollTo({ top: 0, behavior: "instant" });
    closeButton.current?.focus({ preventScroll: true });
    function escape(event: KeyboardEvent) {
      if (event.key === "Escape" && !document.querySelector("dialog[open]")) {
        event.preventDefault();
        setSelection(null);
        restoreTrigger();
      }
    }
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [selected, container]);

  if (!enabled) return children;
  return <InspectorContext.Provider value={{ selected, container, select, clear }}>
    <div className="gp-inspector-layout" data-inspector-open={selected !== null}>
      {children}
      <aside className="gp-inspector" hidden={!selected} role="dialog" aria-modal="false" aria-labelledby="gp-inspector-title">
        <div className="gp-inspector-toolbar"><span>DETAILS &amp; PLAN REVIEW</span><button ref={closeButton} type="button" className="secondary" onClick={close} aria-label="Close details and return to page controls">Back to controls ×</button></div>
        <div ref={setContainer} className="gp-inspector-body" />
      </aside>
    </div>
  </InspectorContext.Provider>;
}

/** Keep nested disclosures inline inside the inspector. Top-level cards open the live React content in the side panel. */
export default function WorkspaceDetails({ children, className, open, autoOpenKey, ...props }: DetailsHTMLAttributes<HTMLDetailsElement> & { autoOpenKey?: string }) {
  const inspector = useContext(InspectorContext);
  const inside = useContext(InsideInspector);
  const id = useId();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const openedKey = useRef<string | undefined>(undefined);
  const lifetime = useRef({ version: 0 });
  const select = inspector?.select;
  const clear = inspector?.clear;
  useEffect(() => {
    if (autoOpenKey && openedKey.current !== autoOpenKey && select && !inside && triggerRef.current) {
      openedKey.current = autoOpenKey;
      select(id, triggerRef.current);
    }
  }, [autoOpenKey, select, inside, id]);
  useEffect(() => {
    const state = lifetime.current;
    const version = ++state.version;
    return () => { queueMicrotask(() => { if (state.version === version) clear?.(id); }); };
  }, [clear, id]);
  if (!inspector || inside) return <details {...props} className={className} open={open}>{children}</details>;
  const parts = Children.toArray(children);
  const summary = parts.find(part => isValidElement(part) && part.type === "summary");
  const title = isValidElement<{ children: ReactNode }>(summary) ? summary.props.children : "Details";
  const content = parts.filter(part => part !== summary);
  return <div id={props.id} className={"gp-detail-card " + (className ?? "")}>
    <button ref={triggerRef} type="button" className="gp-detail-open" data-detail-open aria-expanded={inspector.selected === id}
      aria-controls="gp-inspector-content" onClick={event => {
        const focused = document.activeElement;
        const source = focused instanceof HTMLElement && props.id && focused.dataset.detailTarget === props.id ? focused : event.currentTarget;
        inspector.select(id, source);
      }}>
      <span className="gp-detail-label">{title}</span><span className="gp-detail-chevron" aria-hidden="true">↗</span>
    </button>
    {inspector.selected === id && inspector.container && createPortal(<InsideInspector.Provider value={true}>
      <div id="gp-inspector-content"><h2 id="gp-inspector-title">{title}</h2>{content}</div>
    </InsideInspector.Provider>, inspector.container)}
  </div>;
}
