import TaskItem from "./TaskItem.jsx";

export default function TaskList({ tasks, loading, filter, busyIds, onComplete, onDelete }) {
  if (loading) return <p className="muted">Loading tasks…</p>;
  if (tasks.length === 0) {
    return <p className="muted">{filter === "all" ? "No tasks yet. Add one above." : `No ${filter} tasks.`}</p>;
  }
  return (
    <ul className="task-list">
      {tasks.map((task) => (
        <TaskItem
          key={task.id}
          task={task}
          busy={busyIds.has(task.id)}
          onComplete={() => onComplete(task.id)}
          onDelete={() => onDelete(task.id)}
        />
      ))}
    </ul>
  );
}
