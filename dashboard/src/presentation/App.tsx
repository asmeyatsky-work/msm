// Presentation — React UI. §2: wires adapters into use cases.
import { useEffect, useState } from "react";
import type { ReconciliationRow } from "../domain/reconciliation";
import { residual } from "../domain/reconciliation";
import { LoadReconciliation } from "../application/load-reconciliation";
import { HttpReconciliationGateway } from "../infrastructure/http-gateway";

const gateway = new HttpReconciliationGateway(
  import.meta.env.VITE_RECONCILIATION_API ?? "/api",
);
const useCase = new LoadReconciliation(gateway);

export function App() {
  const [rows, setRows] = useState<ReconciliationRow[]>([]);

  useEffect(() => {
    const now = Date.now();
    const day = 24 * 60 * 60 * 1000;
    useCase.execute(now - 7 * day, now, now).then(({ completed }) => setRows(completed));
  }, []);

  return (
    <main>
      <h1>RPC Reconciliation (7d)</h1>
      <table>
        <thead>
          <tr><th>click_id</th><th>predicted</th><th>realized</th><th>residual</th><th>source</th></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.clickId}>
              <td>{r.clickId}</td>
              <td>{r.predictedRpc.toFixed(2)}</td>
              <td>{r.realizedRpc.toFixed(2)}</td>
              <td>{residual(r).toFixed(2)}</td>
              <td>{r.source}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
