import { requestJson } from "./httpClient";

export const connectCloudApi = {
  id: "connect-cloud",
  method: "POST",
  endpoint: "/api/v1/cloud-accounts",
  title: "Connect Cloud Account",
};

export const listCloudAccountsApi = {
  id: "list-cloud",
  method: "GET",
  endpoint: "/api/v1/cloud-accounts",
  title: "Cloud Accounts",
};

const mockCloudAccounts = [
  {
    id: "ca-901",
    owner_id: "owner-501",
    Organization_id: "org-1001",
    tenant_id: "tenant-prod-778",
    client_id: "client-01fd9",
    subscription_id: "sub-9421-ax9",
    client_secret: "secret-9xk2",
  },
];

export const getCloudAccounts = async () => {
  try {
    return await requestJson(listCloudAccountsApi.endpoint, {
      method: listCloudAccountsApi.method,
    });
  } catch {
    return mockCloudAccounts;
  }
};

export const connectCloudAccount = async (payload) => {
  const createPayload = {
    Organization_id: payload.Organization_id,
    tenant_id: payload.tenant_id,
    client_id: payload.client_id,
    subscription_id: payload.subscription_id,
    client_secret: payload.client_secret,
  };

  try {
    return await requestJson(connectCloudApi.endpoint, {
      method: connectCloudApi.method,
      body: JSON.stringify(createPayload),
    });
  } catch {
    return {
      id: `ca-${Date.now()}`,
      owner_id: "owner-local",
      ...createPayload,
    };
  }
};
