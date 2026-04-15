import { useEffect, useState } from "react";
import { getAuditEvents } from "../api/auditTrail.api";

function AuditTrailPage() {
  const [auditEvents, setAuditEvents] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const loadData = async () => {
      setIsLoading(true);
      setError("");
      try {
        const response = await getAuditEvents();
        setAuditEvents(Array.isArray(response) ? response : []);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load audit trail");
      } finally {
        setIsLoading(false);
      }
    };

    loadData();
  }, []);

  return (
    <section className="card">
      <h2>Audit Trail</h2>
      {isLoading ? <p>Loading...</p> : null}
      {error ? <p>{error}</p> : null}
      {!isLoading && !error ? (
      <ul className="list">
        {auditEvents.map((eventText) => (
          <li key={eventText}>{eventText}</li>
        ))}
      </ul>
      ) : null}
    </section>
  );
}

export default AuditTrailPage;
