"use client";
import React from "react";

// Minimal error boundary so a single bad section shows a readable message instead of
// blanking the whole page. Also surfaces the component stack for debugging.
export class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { error: Error | null; info: string | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { error: null, info: null };
  }
  static getDerivedStateFromError(error: Error) {
    return { error, info: null };
  }
  componentDidCatch(error: Error, info: React.ErrorInfo) {
    this.setState({ error, info: info.componentStack || null });
    // eslint-disable-next-line no-console
    console.error("ErrorBoundary caught:", error, info.componentStack);
  }
  render() {
    if (this.state.error) {
      return (
        <div className="rounded-md border border-negative/40 bg-negative/5 p-4 text-sm text-negative">
          <p className="font-semibold">A section failed to render.</p>
          <p className="mt-1">{String(this.state.error.message || this.state.error)}</p>
          {this.state.info && (
            <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap text-[11px] opacity-80">{this.state.info}</pre>
          )}
        </div>
      );
    }
    return this.props.children;
  }
}
