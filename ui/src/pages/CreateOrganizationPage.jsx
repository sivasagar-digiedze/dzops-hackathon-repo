import { useState } from "react";
import { createOrganization } from "../api/organizations.api";

function CreateOrganizationPage({ onCreated, onCancel }) {
  const [orgForm, setOrgForm] = useState({
    name: "",
    suppoer_email: "",
  });

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!orgForm.name || !orgForm.suppoer_email) return;
    await createOrganization(orgForm);
    setOrgForm({ name: "", suppoer_email: "" });
    onCreated();
  };

  return (
    <section className="card">
      <h2>Create Organization</h2>
      <form className="form-grid" onSubmit={handleSubmit}>
        <label>
          Organization Name
          <input
            type="text"
            value={orgForm.name}
            onChange={(e) => setOrgForm((p) => ({ ...p, name: e.target.value }))}
            placeholder="Example: Nimbus Labs"
          />
        </label>
        <label>
          Support Email
          <input
            type="email"
            value={orgForm.suppoer_email}
            onChange={(e) => setOrgForm((p) => ({ ...p, suppoer_email: e.target.value }))}
            placeholder="support@organization.com"
          />
        </label>
        <div className="form-actions">
          <button type="submit">Create</button>
          <button type="button" className="secondary-btn" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </form>
    </section>
  );
}

export default CreateOrganizationPage;
