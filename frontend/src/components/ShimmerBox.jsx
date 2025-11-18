export default function ShimmerBox({ height = "h-6", width = "w-full", className = "" }) {
  return (
    <div
      className={`shimmer rounded-lg ${height} ${width} bg-white/5 ${className}`}
    />
  );
}
