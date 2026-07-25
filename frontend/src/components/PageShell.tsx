import type { ReactNode } from "react";

export type PageShellProps = {
  children: ReactNode;
  headerActions?: ReactNode;
};

export function PageShell({ children, headerActions }: PageShellProps) {
  return (
    <div className="page-shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <header className="site-header">
        <div className="site-header__content">
          <span>A Penny Saved</span>
          {headerActions}
        </div>
      </header>
      <main className="page-content" id="main-content" tabIndex={-1}>
        {children}
      </main>
    </div>
  );
}
