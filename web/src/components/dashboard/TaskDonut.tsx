import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { Card, SectionHeader } from "../ui/primitives";

export default function TaskDonut({
  total,
  segments,
}: {
  total: number;
  segments: { key: string; label: string; value: number; color: string }[];
}) {
  const data = segments.filter((item) => item.value > 0);
  return (
    <Card className="flex h-full flex-col">
      <SectionHeader
        title="任务概览"
        action={
          <select className="rounded-lg border border-ink-700 bg-ink-900/60 px-2 py-1 text-[11px] text-mist-300 outline-none">
            <option>本周</option>
            <option>本月</option>
          </select>
        }
      />
      <div className="flex min-h-[230px] flex-1 items-center gap-3">
        <div className="relative h-[230px] min-w-0 flex-1">
          <ResponsiveContainer width="100%" height="100%" minWidth={0}>
            <PieChart>
              <Pie
                data={data}
                dataKey="value"
                nameKey="label"
                cx="50%"
                cy="50%"
                innerRadius={66}
                outerRadius={94}
                paddingAngle={3}
                stroke="none"
                startAngle={90}
                endAngle={-270}
                isAnimationActive={false}
              >
                {data.map((entry) => (
                  <Cell key={entry.key} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  background: "#0B1426",
                  border: "1px solid #24365A",
                  borderRadius: 10,
                  color: "#E6ECF7",
                  fontSize: 12,
                }}
                itemStyle={{ color: "#E6ECF7" }}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-[28px] font-semibold leading-none text-mist-100">
              {total}
            </span>
            <span className="mt-1.5 text-[11px] text-mist-500">总任务</span>
          </div>
        </div>
        <div className="w-[132px] shrink-0 space-y-2.5">
          {segments.map((item) => {
            const percent = total ? Math.round((item.value / total) * 100) : 0;
            return (
              <div key={item.key} className="flex items-center gap-2 text-[11.5px]">
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ background: item.color }}
                />
                <span className="flex-1 text-mist-300">{item.label}</span>
                <span className="w-5 text-right text-mist-100">{item.value}</span>
                <span className="w-8 text-right text-mist-500">{percent}%</span>
              </div>
            );
          })}
        </div>
      </div>
    </Card>
  );
}
