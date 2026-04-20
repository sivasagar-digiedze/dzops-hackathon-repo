import { requestJson } from "./httpClient";

export const listTicketsApi = {
  id: "tickets",
  method: "GET",
  endpoint: "/api/tickets",
  title: "List Tickets",
};

const mockTickets = [
  { id: "T-102", title: "Rotate access keys", status: "In Progress" },
  { id: "T-107", title: "S3 bucket policy review", status: "Open" },
  { id: "T-115", title: "Enable MFA for IAM users", status: "Closed" },
];

export const getTickets = async () => {
  try {
    return await requestJson(listTicketsApi.endpoint, {
      method: listTicketsApi.method,
    });
  } catch {
    return mockTickets;
  }
};
