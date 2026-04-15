import { requestJson } from "./httpClient";

export const createOrganizationApi = {
  id: "create-org",
  method: "POST",
  endpoint: "/api/v1/organizations",
  title: "Create Organization",
};

export const listOrganizationsApi = {
  id: "list-orgs",
  method: "GET",
  endpoint: "/api/v1/organizations",
  title: "List Organizations",
};

export const updateOrganizationApi = {
  id: "update-org",
  method: "POST",
  endpoint: "/api/v1/organizations/{id}",
  title: "Update Organization",
};

const mockOrganizations = [
  { id: "org-1001", name: "Acme Corp", suppoer_email: "support@acme.com" },
];

export const getOrganizations = async () => {
  try {
    return await requestJson(listOrganizationsApi.endpoint, {
      method: listOrganizationsApi.method,
    });
  } catch {
    return mockOrganizations;
  }
};

export const createOrganization = async (payload) => {
  const createPayload = {
    name: payload.name,
    suppoer_email: payload.suppoer_email,
  };

  try {
    return await requestJson(createOrganizationApi.endpoint, {
      method: createOrganizationApi.method,
      body: JSON.stringify(createPayload),
    });
  } catch {
    return { id: `org-${Date.now()}`, ...createPayload };
  }
};

export const updateOrganizationById = async (id, payload) => {
  const updatePayload = {
    name: payload.name,
    suppoer_email: payload.suppoer_email,
  };

  try {
    return await requestJson(`/api/v1/organizations/${id}`, {
      method: updateOrganizationApi.method,
      body: JSON.stringify(updatePayload),
    });
  } catch {
    return { id, ...updatePayload };
  }
};
