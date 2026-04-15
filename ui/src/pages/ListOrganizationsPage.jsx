import { useEffect, useState } from "react";
import { getOrganizations } from "../api/organizations.api";

function ListOrganizationsPage({ onAddOrganization }) {
  const [organizations, setOrganizations] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  const loadData = async () => {
    setIsLoading(true);
    setError("");
    try {
      const response = await getOrganizations();
      setOrganizations(Array.isArray(response) ? response : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load organizations");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  return (
    <section className="card">
      <div className="section-header">
        <h2>Organization</h2>
        <button type="button" onClick={onAddOrganization}>
          Add Organization
        </button>
      </div>
      {isLoading ? <p>Loading...</p> : null}
      {error ? <p>{error}</p> : null}
      {!isLoading && !error ? (
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Name</th>
              <th>Support Email</th>
            </tr>
          </thead>
          <tbody>
            {organizations.map((org) => (
              <tr key={org.id ?? `${org.name}-${org.suppoer_email}`}>
                <td>{org.id ?? "-"}</td>
                <td>{org.name}</td>
                <td>{org.suppoer_email ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}

export default ListOrganizationsPage;
