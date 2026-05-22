import React from "react";

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error("ErrorBoundary caught:", error, info);
  }

  render() {
    if (this.state.error) {
      const err = this.state.error;
      return (
        <div style={{ padding: 24, color: "#ffe4e6", background: "#2b2a2e", minHeight: "100vh" }}>
          <h2 style={{ marginBottom: 8 }}>Application error</h2>
          <p style={{ color: "#fca5a5" }}>{err && err.message}</p>
          <details style={{ whiteSpace: "pre-wrap", marginTop: 12 }}>
            {err && err.stack}
          </details>
        </div>
      );
    }

    return this.props.children;
  }
}
