export default function DashboardCard({ title, children, right }) {
  return (
    <div className="card relative overflow-hidden">
      <div className="absolute -top-24 -right-24 w-72 h-72 rounded-full bg-indigo-500/10 blur-3xl" />
      <div className="flex items-center justify-between mb-3">
        <h2 className="section-title">{title}</h2>
        {right}
      </div>
      <div>{children}</div>
    </div>
  );
}
