import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import "./CodeAgent.css";

const SUGGESTIONS = [
  "Write a Python function to validate email addresses",
  "Create a FastAPI health check endpoint",
  "Add error handling to a file read utility",
  "Write a bash script to backup a PostgreSQL database",
];

function BackendTag({ backend, usedNous }) {
  if (backend === "nous_hermes" || usedNous) {
    return <span className="code-badge-nous">Nous Hermes</span>;
  }
  if (backend === "openai") {
    return <span className="code-badge-gpt">OpenAI</span>;
  }
  return null;
}

function LineNumbers({ code }) {
  const lines = (code || "").split("\n");
  return (
    <div className="code-editor-gutter" aria-hidden="true">
      {lines.map((_, i) => (
        <div key={i}>{i + 1}</div>
      ))}
    </div>
  );
}

export default function CodeAgent({ health, onError, onSuccess }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [activeResult, setActiveResult] = useState(null);
  const [copied, setCopied] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const [options, setOptions] = useState({
    language: "python",
    backend: "nous_hermes",
    context: "",
    read_paths: "",
    write_file: false,
    output_path: "",
    run_tests: true,
    test_command: "",
  });

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading, scrollToBottom]);

  const canSend =
    input.trim().length >= 3 &&
    !loading &&
    !(options.backend === "nous_hermes" && !health?.nous_hermes_configured && !health?.gpt_enabled);

  const submit = async (commandText) => {
    const command = (commandText || input).trim();
    if (command.length < 3 || loading) return;

    setInput("");
    setLoading(true);
    setActiveResult(null);

    const userMsg = { id: Date.now(), role: "user", text: command };
    setMessages((prev) => [...prev, userMsg]);

    try {
      const result = await api.createCode({
        command,
        language: options.language || null,
        context: options.context.trim() || null,
        read_paths: options.read_paths
          ? options.read_paths.split(",").map((p) => p.trim()).filter(Boolean)
          : null,
        write_file: options.write_file,
        output_path: options.write_file ? options.output_path || null : null,
        run_tests: options.run_tests,
        test_command: options.test_command.trim() || null,
        backend: options.backend || null,
      });

      setActiveResult(result);
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          role: "assistant",
          text: result.explanation || (result.success ? "Code generated successfully." : "Generation failed."),
          result,
        },
      ]);

      if (result.written_path) onSuccess?.(`Saved to ${result.written_path}`);
      if (result.success === false) onError?.(new Error("Tests failed — see output panel"));
    } catch (err) {
      onError?.(err);
      setMessages((prev) => [
        ...prev,
        { id: Date.now() + 1, role: "assistant", text: `Error: ${err.message}`, error: true },
      ]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (canSend) submit();
    }
  };

  const copyCode = async () => {
    if (!activeResult?.code) return;
    try {
      await navigator.clipboard.writeText(activeResult.code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      onError?.(new Error("Could not copy to clipboard"));
    }
  };

  const modelLabel = health?.model || "—";
  const backendLabel = health?.code_agent_backend || options.backend;

  return (
    <div className="code-workspace">
      <header className="code-toolbar">
        <div className="code-toolbar-left">
          <span className="code-toolbar-title">Code Agent</span>
          <span className="code-toolbar-meta">
            {backendLabel} · {modelLabel}
            {health?.nous_hermes_configured ? " · ready" : " · configure keys"}
          </span>
        </div>
        <div className="code-toolbar-right">
          <button
            type="button"
            className={`code-toolbar-btn ${showSettings ? "active" : ""}`}
            onClick={() => setShowSettings((s) => !s)}
          >
            Settings
          </button>
        </div>
      </header>

      {showSettings && (
        <div className="code-settings-drawer">
          <div>
            <label>Backend</label>
            <select
              value={options.backend}
              onChange={(e) => setOptions({ ...options, backend: e.target.value })}
            >
              <option value="nous_hermes">Nous Hermes</option>
              <option value="openai">OpenAI GPT</option>
            </select>
          </div>
          <div>
            <label>Language</label>
            <input
              value={options.language}
              onChange={(e) => setOptions({ ...options, language: e.target.value })}
              placeholder="python"
            />
          </div>
          <div>
            <label>Read paths (comma-separated)</label>
            <input
              value={options.read_paths}
              onChange={(e) => setOptions({ ...options, read_paths: e.target.value })}
              placeholder="hermes/code_agent/agent.py"
            />
          </div>
          <div>
            <label>Context</label>
            <textarea
              value={options.context}
              onChange={(e) => setOptions({ ...options, context: e.target.value })}
              placeholder="Existing code or requirements..."
            />
          </div>
          <div>
            <label className="code-settings-check">
              <input
                type="checkbox"
                checked={options.write_file}
                onChange={(e) => setOptions({ ...options, write_file: e.target.checked })}
              />
              Save to file
            </label>
            {options.write_file && (
              <input
                style={{ marginTop: "0.35rem" }}
                value={options.output_path}
                onChange={(e) => setOptions({ ...options, output_path: e.target.value })}
                placeholder="hermes/code_agent/generated.py"
              />
            )}
            <label className="code-settings-check">
              <input
                type="checkbox"
                checked={options.run_tests}
                onChange={(e) => setOptions({ ...options, run_tests: e.target.checked })}
              />
              Run tests
            </label>
            {options.run_tests && (
              <input
                style={{ marginTop: "0.35rem" }}
                value={options.test_command}
                onChange={(e) => setOptions({ ...options, test_command: e.target.value })}
                placeholder="Optional test command"
              />
            )}
          </div>
        </div>
      )}

      <div className="code-panels">
        <section className="code-chat-panel">
          <div className="code-messages">
            {messages.length === 0 && !loading && (
              <div className="code-empty">
                <div className="code-empty-icon">{`</>`}</div>
                <h2>Ask Hermes to write code</h2>
                <p>
                  Cursor-style agent chat. Describe what to build — Nous Hermes runs terminal,
                  file, and test tools when needed.
                </p>
                <div className="code-suggestions">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      type="button"
                      className="code-suggestion"
                      onClick={() => {
                        setInput(s);
                        inputRef.current?.focus();
                      }}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg) => (
              <div key={msg.id} className={`code-msg code-msg-${msg.role}`}>
                <div className="code-msg-label">{msg.role === "user" ? "You" : "Hermes"}</div>
                <div className={`code-msg-bubble ${msg.error ? "code-badge-fail" : ""}`}>
                  {msg.text}
                </div>
                {msg.result && (
                  <div className="code-msg-meta">
                    <BackendTag backend={msg.result.backend} usedNous={msg.result.used_nous_hermes} />
                    <span className={msg.result.success ? "code-badge-ok" : "code-badge-fail"}>
                      {msg.result.success ? "Success" : "Failed"}
                    </span>
                    <span>{msg.result.filename}</span>
                    {msg.result.written_path && <span>{msg.result.written_path}</span>}
                  </div>
                )}
                {msg.result?.steps?.length > 0 && (
                  <div className="code-msg-steps">
                    {msg.result.steps.map((s, i) => (
                      <span key={i} className={`code-step ${s.status}`} title={s.detail}>
                        {s.step}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="code-loading">
                <span>Generating</span>
                <span className="code-loading-dots">
                  <span>.</span>
                  <span>.</span>
                  <span>.</span>
                </span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="code-composer-wrap">
            <div className="code-composer">
              <textarea
                ref={inputRef}
                className="code-composer-input"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask Hermes to generate or fix code… (Enter to send, Shift+Enter for newline)"
                rows={3}
                disabled={loading}
              />
              <div className="code-composer-bar">
                <div className="code-composer-left">
                  <select
                    className="code-toolbar-select"
                    value={options.backend}
                    onChange={(e) => setOptions({ ...options, backend: e.target.value })}
                  >
                    <option value="nous_hermes">Nous Hermes</option>
                    <option value="openai">OpenAI</option>
                  </select>
                  <select
                    className="code-toolbar-select"
                    value={options.language}
                    onChange={(e) => setOptions({ ...options, language: e.target.value })}
                  >
                    <option value="python">Python</option>
                    <option value="javascript">JavaScript</option>
                    <option value="typescript">TypeScript</option>
                    <option value="bash">Bash</option>
                    <option value="sql">SQL</option>
                  </select>
                  <span className="code-composer-hint">Enter ↵ send</span>
                </div>
                <button
                  type="button"
                  className="code-send-btn"
                  disabled={!canSend}
                  onClick={() => submit()}
                >
                  Send ↑
                </button>
              </div>
            </div>
          </div>
        </section>

        <section className="code-editor-panel">
          <div className="code-editor-tabs">
            <div className={`code-editor-tab ${activeResult ? "" : "code-editor-tab-idle"}`}>
              {activeResult?.filename || "output"}
            </div>
            <div className="code-editor-actions">
              {activeResult?.code && (
                <button type="button" className="code-icon-btn" onClick={copyCode}>
                  {copied ? "Copied!" : "Copy"}
                </button>
              )}
            </div>
          </div>

          {activeResult?.code ? (
            <div className="code-editor-body">
              <LineNumbers code={activeResult.code} />
              <pre className="code-editor-content">
                <code>{activeResult.code}</code>
              </pre>
            </div>
          ) : (
            <div className="code-editor-empty">Generated code will appear here</div>
          )}

          <footer className="code-editor-footer">
            {activeResult ? (
              <>
                {activeResult.language} · {activeResult.filename}
                {activeResult.written_path ? ` · saved ${activeResult.written_path}` : ""}
                {activeResult.analysis && (
                  <div style={{ marginTop: "0.35rem", color: "#858585" }}>
                    {activeResult.analysis.slice(0, 200)}
                    {activeResult.analysis.length > 200 ? "…" : ""}
                  </div>
                )}
                {activeResult.test_output && (
                  <div className="code-terminal-out">{activeResult.test_output}</div>
                )}
              </>
            ) : (
              "Editor preview — run a prompt to generate code"
            )}
          </footer>
        </section>
      </div>
    </div>
  );
}
