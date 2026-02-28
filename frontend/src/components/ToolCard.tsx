import { FormEvent, useState } from "react";
import { Card } from "./ui/card";

type Field = {
  key: string;
  label: string;
  defaultValue: string;
};

type Props = {
  title: string;
  description: string;
  fields: Field[];
  onSubmit: (values: Record<string, string>) => Promise<void>;
  result: Record<string, unknown> | null;
};

export function ToolCard({ title, description, fields, onSubmit, result }: Props) {
  const [values, setValues] = useState<Record<string, string>>(
    Object.fromEntries(fields.map((field) => [field.key, field.defaultValue]))
  );
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    try {
      await onSubmit(values);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <div className="mb-4">
        <h2 className="text-lg font-semibold">{title}</h2>
        <p className="text-sm text-stone-600">{description}</p>
      </div>

      <form className="grid gap-3" onSubmit={handleSubmit}>
        {fields.map((field) => (
          <label key={field.key} className="grid gap-1">
            <span className="text-sm font-medium">{field.label}</span>
            <input
              className="rounded-md border border-stone-300 bg-white px-3 py-2 text-sm"
              value={values[field.key] ?? ""}
              onChange={(e) => setValues((prev) => ({ ...prev, [field.key]: e.target.value }))}
            />
          </label>
        ))}
        <button
          type="submit"
          className="rounded-md bg-stone-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
          disabled={loading}
        >
          {loading ? "Running..." : "Run Tool"}
        </button>
      </form>

      {result && (
        <div className="mt-4 grid gap-3">
          <div>
            <h3 className="mb-2 text-sm font-semibold">JSON Result</h3>
            <pre className="max-h-72 overflow-auto rounded-md bg-stone-950 p-3 text-xs text-stone-100">
              {JSON.stringify(result, null, 2)}
            </pre>
          </div>

          {"result" in result && typeof result.result === "object" && result.result && (
            <div>
              <h3 className="mb-2 text-sm font-semibold">Quick View</h3>
              <div className="overflow-auto rounded-md border border-stone-300">
                <table className="min-w-full text-left text-xs">
                  <tbody>
                    {Object.entries(result.result as Record<string, unknown>).map(([key, value]) => (
                      <tr key={key} className="border-t border-stone-200">
                        <td className="px-3 py-2 font-medium">{key}</td>
                        <td className="px-3 py-2">{typeof value === "object" ? JSON.stringify(value) : String(value)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
