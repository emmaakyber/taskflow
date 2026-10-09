import { useState } from "react";

export default function TaskForm({ onCreate }) {
  const [title, setTitle] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await onCreate(title);
      setTitle("");
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form className="task-form" onSubmit={submit}>
      <label htmlFor="new-task" className="sr-only">New task title</label>
      <input
        id="new-task"
        type="text"
        placeholder="What needs doing?"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        maxLength={200}
        autoFocus
      />
      <button type="submit" disabled={submitting || !title.trim()}>
        {submitting ? "Adding…" : "Add"}
      </button>
      {error && <p className="field-error" role="alert">{error}</p>}
    </form>
  );
}
