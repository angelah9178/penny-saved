import { useRef, type MouseEvent, type ReactNode } from "react";

export type PageShellProps = {
  children: ReactNode;
  headerActions?: ReactNode;
};

export function PageShell({ children, headerActions }: PageShellProps) {
  const mainRef = useRef<HTMLElement>(null);

  function skipToMain(event: MouseEvent<HTMLAnchorElement>): void {
    event.preventDefault();
    mainRef.current?.focus();
  }

  return (
    <div className="page-shell">
      <a className="skip-link" href="#main-content" onClick={skipToMain}>
        Skip to main content
      </a>
      <header className="site-header">
        <div className="site-header__content">
          <span>A Penny Saved</span>
          {headerActions}
        </div>
      </header>
      <main
        className="page-content"
        id="main-content"
        ref={mainRef}
        tabIndex={-1}
      >
        {children}
      </main>
    </div>
  );
}
