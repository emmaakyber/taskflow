const FILTERS = ["all", "pending", "completed"];

export default function FilterTabs({ value, onChange }) {
  return (
    <div className="filters" role="tablist" aria-label="Filter tasks">
      {FILTERS.map((f) => (
        <button
          key={f}
          role="tab"
          aria-selected={value === f}
          className={value === f ? "tab active" : "tab"}
          onClick={() => onChange(f)}
        >
          {f[0].toUpperCase() + f.slice(1)}
        </button>
      ))}
    </div>
  );
}
