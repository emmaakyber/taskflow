export default function TaskItem({ task, busy, onComplete, onUndo, onDelete }) {
  return (
    <li className={task.completed ? "task done" : "task"}>
      <div className="task-main">
        <span className="task-status" aria-label={task.completed ? "Completed" : "Pending"}>
          {task.completed ? "✓" : "○"}
        </span>
        <span className="task-title">{task.title}</span>
      </div>
      <div className="task-actions">
        {task.completed ? (
          <button onClick={onUndo} disabled={busy} title="Mark as pending again">Undo</button>
        ) : (
          <button onClick={onComplete} disabled={busy}>Complete</button>
        )}
        <button className="danger" onClick={onDelete} disabled={busy}>Delete</button>
      </div>
    </li>
  );
}
