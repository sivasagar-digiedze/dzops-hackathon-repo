import { useEffect, useState } from "react";
import { getTickets } from "../api/tickets.api";

function TicketsPage() {
  const [tickets, setTickets] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const loadData = async () => {
      setIsLoading(true);
      setError("");
      try {
        const response = await getTickets();
        setTickets(Array.isArray(response) ? response : []);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load tickets");
      } finally {
        setIsLoading(false);
      }
    };

    loadData();
  }, []);

  return (
    <section className="card">
      <h2>List Tickets</h2>
      {isLoading ? <p>Loading...</p> : null}
      {error ? <p>{error}</p> : null}
      {!isLoading && !error ? (
      <table>
        <thead>
          <tr>
            <th>Ticket ID</th>
            <th>Title</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {tickets.map((ticket) => (
            <tr key={ticket.id}>
              <td>{ticket.id}</td>
              <td>{ticket.title}</td>
              <td>{ticket.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
      ) : null}
    </section>
  );
}

export default TicketsPage;
