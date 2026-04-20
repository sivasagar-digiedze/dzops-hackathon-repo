import { useState } from "react";
import { connectCloudAccount } from "../api/cloudAccounts.api";

function ConnectCloudPage({ onConnected, onCancel }) {
  const [cloudForm, setCloudForm] = useState({
    Organization_id: "",
    tenant_id: "",
    client_id: "",
    subscription_id: "",
    client_secret: "",
  });

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (
      !cloudForm.Organization_id ||
      !cloudForm.tenant_id ||
      !cloudForm.client_id ||
      !cloudForm.subscription_id ||
      !cloudForm.client_secret
    ) {
      return;
    }
    await connectCloudAccount(cloudForm);
    setCloudForm({
      Organization_id: "",
      tenant_id: "",
      client_id: "",
      subscription_id: "",
      client_secret: "",
    });
    onConnected();
  };

  return (
    <section className="card">
      <h2>Connect Cloud Account</h2>
      <form className="form-grid" onSubmit={handleSubmit}>
        <label>
          Organization ID
          <input
            type="text"
            value={cloudForm.Organization_id}
            onChange={(e) => setCloudForm((p) => ({ ...p, Organization_id: e.target.value }))}
            placeholder="Enter organization ID"
          />
        </label>
        <label>
          Tenant ID
          <input
            type="text"
            value={cloudForm.tenant_id}
            onChange={(e) => setCloudForm((p) => ({ ...p, tenant_id: e.target.value }))}
            placeholder="Enter tenant ID"
          />
        </label>
        <label>
          Client ID
          <input
            type="text"
            value={cloudForm.client_id}
            onChange={(e) => setCloudForm((p) => ({ ...p, client_id: e.target.value }))}
            placeholder="Enter client ID"
          />
        </label>
        <label>
          Subscription ID
          <input
            type="text"
            value={cloudForm.subscription_id}
            onChange={(e) => setCloudForm((p) => ({ ...p, subscription_id: e.target.value }))}
            placeholder="Enter subscription ID"
          />
        </label>
        <label>
          Client Secret
          <input
            type="password"
            value={cloudForm.client_secret}
            onChange={(e) => setCloudForm((p) => ({ ...p, client_secret: e.target.value }))}
            placeholder="Enter client secret"
          />
        </label>
        <div className="form-actions">
          <button type="submit">Connect</button>
          <button type="button" className="secondary-btn" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </form>
    </section>
  );
}

export default ConnectCloudPage;
