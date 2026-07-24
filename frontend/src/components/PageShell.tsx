import type { ReactNode } from "react";

export type PageShellProps = {
  children: ReactNode;
};

export function PageShell({ children }: PageShellProps) {
  return (
    <div className="page-shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <header className="site-header">
        <div className="site-header__content">A Penny Saved</div>
      </header>
      <main className="page-content" id="main-content" tabIndex={-1}>
        {children}
      </main>
    </div>
  );
}
