import { requestJson } from "./httpClient";

export const listAuditTrailApi = {
  id: "audit-trail",
  method: "GET",
  endpoint: "/api/audit-trail",
  title: "Audit Trail",
};

const mockAuditEvents = [
  "Organization Acme Corp created by admin",
  "Cloud account AWS-Primary linked successfully",
  "Ticket #T-102 moved to In Progress",
];

export const getAuditEvents = async () => {
  try {
    return await requestJson(listAuditTrailApi.endpoint, {
      method: listAuditTrailApi.method,
    });
  } catch {
    return mockAuditEvents;
  }
};
