import { useEffect, useState } from "react";

export function ConnectionStatus() {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<"checking" | "ready" | "unavailable">(
    "checking",
  );
  useEffect(() => {
    let disposed = false;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 8000);
    setState("checking");
    fetch("/api/health", { signal: controller.signal, cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error("Unavailable");
        const health: unknown = await response.json();
        if (
          typeof health !== "object" ||
          health === null ||
          !("status" in health) ||
          !("database" in health) ||
          health.status !== "ok" ||
          health.database !== "ok"
        )
          throw new Error("Invalid health response");
        if (!disposed) setState("ready");
      })
      .catch(() => {
        if (!disposed) setState("unavailable");
      })
      .finally(() => window.clearTimeout(timer));
    return () => {
      disposed = true;
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [attempt]);

  return (
    <div className="connection">
      <span role="status" aria-label="服务连接状态">
        {state === "checking"
          ? "正在连接服务…"
          : state === "ready"
            ? "服务连接正常"
            : "服务暂不可用"}
      </span>
      {state === "unavailable" && (
        <button onClick={() => setAttempt((value) => value + 1)}>
          重试连接
        </button>
      )}
    </div>
  );
}
