import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "./api.js";
import TaskForm from "./components/TaskForm.jsx";
import TaskList from "./components/TaskList.jsx";
import Stats from "./components/Stats.jsx";
import FilterTabs from "./components/FilterTabs.jsx";

export default function App() {
  const [tasks, setTasks] = useState([]);
  const [stats, setStats] = useState(null);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busyIds, setBusyIds] = useState(new Set());
  const requestSeq = useRef(0);

  // Tasks and stats are fetched together after every change. Stats come from
  // the API's own /tasks/stats rather than being derived client-side, so the
  // numbers shown are always the server's numbers.
  // A sequence number guards against a slow earlier response (e.g. from a
  // previous filter) landing after a newer one and overwriting it.
  const refresh = useCallback(async () => {
    const seq = ++requestSeq.current;
    try {
      const [nextTasks, nextStats] = await Promise.all([api.listTasks(filter), api.getStats()]);
      if (seq !== requestSeq.current) return;
      setTasks(nextTasks);
      setStats(nextStats);
      setError(null);
    } catch (err) {
      if (seq === requestSeq.current) setError(err.message);
    } finally {
      if (seq === requestSeq.current) setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const withBusy = async (id, action) => {
    setBusyIds((prev) => new Set(prev).add(id));
    try {
      await action();
    } catch (err) {
      setError(err.message);
    } finally {
      await refresh(); // even after a failure (e.g. 404), show the server's current state
      setBusyIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  };

  const handleCreate = async (title) => {
    await api.createTask(title); // errors propagate to the form for inline display
    await refresh();
  };
  const handleComplete = (id) => withBusy(id, () => api.completeTask(id));
  const handleUndo = (id) => withBusy(id, () => api.updateTask(id, { completed: false }));
  const handleDelete = (id) => withBusy(id, () => api.deleteTask(id));

  return (
    <main className="app">
      <header>
        <h1>TaskFlow</h1>
        <p className="subtitle">A small task manager. Flask API, React UI.</p>
      </header>

      <Stats stats={stats} />

      <TaskForm onCreate={handleCreate} />

      {error && (
        <div className="banner error" role="alert">
          {error}
          <button className="link" onClick={refresh}>Retry</button>
        </div>
      )}

      <FilterTabs value={filter} onChange={setFilter} />

      <TaskList
        tasks={tasks}
        loading={loading}
        filter={filter}
        busyIds={busyIds}
        onComplete={handleComplete}
        onUndo={handleUndo}
        onDelete={handleDelete}
      />
    </main>
  );
}
