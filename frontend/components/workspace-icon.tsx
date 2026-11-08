export default function WorkspaceIcon({ kind }: { kind: "code" | "rules" | "links" | "tests" | "signals" | "export" }) {
  const paths = {
    code: <><path d="m8 6-6 6 6 6m8-12 6 6-6 6m-3-15-2 18" /></>,
    rules: <><path d="m12 2 10 6-10 6L2 8Zm-10 10 10 6 10-6M2 16l10 6 10-6" /></>,
    links: <><path d="m11 5-6 12m8-12 6 12M6 19h12" /><circle cx="12" cy="4" r="2" /><circle cx="4" cy="20" r="2" /><circle cx="20" cy="20" r="2" /></>,
    tests: <><path d="m6 12 4 4 8-9" /><circle cx="12" cy="12" r="10" /></>,
    signals: <><path d="M2 18 6 9l5 6 5-12 6 10M2 22h20" /></>,
    export: <><path d="M13 2H5v20h14V8ZM13 2v6h6M8 12h8m-8 4h8" /></>,
  };
  return <span className="gp-bubble-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.35" strokeLinecap="round" strokeLinejoin="round">{paths[kind]}</svg></span>;
}
