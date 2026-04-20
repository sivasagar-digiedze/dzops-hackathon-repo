import { useEffect, useState } from "react";
import { getCloudAccounts } from "../api/cloudAccounts.api";

function ListCloudAccountsPage({ onAddCloudAccount }) {
  const [cloudAccounts, setCloudAccounts] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const loadData = async () => {
      setIsLoading(true);
      setError("");
      try {
        const response = await getCloudAccounts();
        setCloudAccounts(Array.isArray(response) ? response : []);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load cloud accounts");
      } finally {
        setIsLoading(false);
      }
    };

    loadData();
  }, []);

  return (
    <section className="card">
      <div className="section-header">
        <h2>Cloud Accounts</h2>
        <button type="button" onClick={onAddCloudAccount}>
          Connect Cloud Account
        </button>
      </div>
      {isLoading ? <p>Loading...</p> : null}
      {error ? <p>{error}</p> : null}
      {!isLoading && !error ? (
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Owner ID</th>
            <th>Organization ID</th>
            <th>Tenant ID</th>
            <th>Client ID</th>
            <th>Subscription ID</th>
            <th>Client Secret</th>
          </tr>
        </thead>
        <tbody>
          {cloudAccounts.map((account) => (
            <tr key={account.id ?? `${account.subscription_id}-${account.client_id}`}>
              <td>{account.id ?? "-"}</td>
              <td>{account.owner_id ?? "-"}</td>
              <td>{account.Organization_id ?? "-"}</td>
              <td>{account.tenant_id ?? "-"}</td>
              <td>{account.client_id ?? "-"}</td>
              <td>{account.subscription_id ?? "-"}</td>
              <td>{account.client_secret ?? "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      ) : null}
    </section>
  );
}

export default ListCloudAccountsPage;
