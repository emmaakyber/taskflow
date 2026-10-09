export default function Stats({ stats }) {
  const cells = [
    ["Total", stats?.total],
    ["Completed", stats?.completed],
    ["Pending", stats?.pending],
  ];
  return (
    <section className="stats" aria-label="Task statistics" aria-live="polite">
      {cells.map(([label, value]) => (
        <div className="stat" key={label}>
          <span className="stat-value">{value ?? "–"}</span>
          <span className="stat-label">{label}</span>
        </div>
      ))}
    </section>
  );
}
