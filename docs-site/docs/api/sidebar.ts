import type { SidebarsConfig } from "@docusaurus/plugin-content-docs";

const sidebar: SidebarsConfig = {
  apisidebar: [
    {
      type: "doc",
      id: "api/simswarm",
    },
    {
      type: "category",
      label: "jobs",
      items: [
        {
          type: "doc",
          id: "api/create-share-link-api-jobs-job-id-share-post",
          label: "Create Share Link",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/revoke-share-link-api-jobs-job-id-share-delete",
          label: "Revoke Share Link",
          className: "api-method delete",
        },
        {
          type: "doc",
          id: "api/create-draft-api-jobs-draft-post",
          label: "Create Draft",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/update-draft-api-jobs-draft-job-id-patch",
          label: "Update Draft",
          className: "api-method patch",
        },
        {
          type: "doc",
          id: "api/launch-draft-api-jobs-draft-job-id-launch-post",
          label: "Launch Draft",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/retry-job-api-jobs-job-id-retry-post",
          label: "Retry Job",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/retry-enrichment-api-jobs-job-id-enrich-retry-post",
          label: "Retry Enrichment",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/create-job-api-jobs-post",
          label: "Create Job",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/list-jobs-api-jobs-get",
          label: "List Jobs",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/get-sim-data-api-jobs-job-id-sim-data-get",
          label: "Get Sim Data",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/get-job-api-jobs-job-id-get",
          label: "Get Job",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/delete-job-api-jobs-job-id-delete",
          label: "Delete Job",
          className: "api-method delete",
        },
        {
          type: "doc",
          id: "api/get-job-graph-api-jobs-job-id-graph-get",
          label: "Get Job Graph",
          className: "api-method get",
        },
      ],
    },
    {
      type: "category",
      label: "drafts",
      items: [
        {
          type: "doc",
          id: "api/create-draft-api-jobs-draft-post",
          label: "Create Draft",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/update-draft-api-jobs-draft-job-id-patch",
          label: "Update Draft",
          className: "api-method patch",
        },
        {
          type: "doc",
          id: "api/launch-draft-api-jobs-draft-job-id-launch-post",
          label: "Launch Draft",
          className: "api-method post",
        },
      ],
    },
    {
      type: "category",
      label: "auth",
      items: [
        {
          type: "doc",
          id: "api/register-api-auth-register-post",
          label: "Register",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/login-api-auth-login-post",
          label: "Login",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/verify-email-api-auth-verify-get",
          label: "Verify Email",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/forgot-password-api-auth-forgot-password-post",
          label: "Forgot Password",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "api/reset-password-api-auth-reset-password-post",
          label: "Reset Password",
          className: "api-method post",
        },
      ],
    },
    {
      type: "category",
      label: "progress",
      items: [
        {
          type: "doc",
          id: "api/job-progress-stream-api-jobs-job-id-progress-get",
          label: "Job Progress Stream",
          className: "api-method get",
        },
      ],
    },
    {
      type: "category",
      label: "export",
      items: [
        {
          type: "doc",
          id: "api/export-pdf-api-jobs-job-id-export-pdf-get",
          label: "Export Pdf",
          className: "api-method get",
        },
      ],
    },
    {
      type: "category",
      label: "share",
      items: [
        {
          type: "doc",
          id: "api/list-demos-api-share-demos-get",
          label: "List Demos",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/get-shared-result-api-share-token-get",
          label: "Get Shared Result",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/get-shared-og-page-api-share-token-og-get",
          label: "Get Shared Og Page",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/get-shared-graph-api-share-token-graph-get",
          label: "Get Shared Graph",
          className: "api-method get",
        },
      ],
    },
    {
      type: "category",
      label: "fetch",
      items: [
        {
          type: "doc",
          id: "api/fetch-url-api-fetch-post",
          label: "Fetch Url",
          className: "api-method post",
        },
      ],
    },
    {
      type: "category",
      label: "profile",
      items: [
        {
          type: "doc",
          id: "api/change-password-api-profile-password-put",
          label: "Change Password",
          className: "api-method put",
        },
        {
          type: "doc",
          id: "api/delete-account-api-profile-account-delete",
          label: "Delete Account",
          className: "api-method delete",
        },
      ],
    },
    {
      type: "category",
      label: "ai",
      items: [
        {
          type: "doc",
          id: "api/generate-goal-api-ai-generate-goal-post",
          label: "Generate Goal",
          className: "api-method post",
        },
      ],
    },
    {
      type: "category",
      label: "UNTAGGED",
      items: [
        {
          type: "doc",
          id: "api/health-api-health-get",
          label: "Health",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "api/public-config-api-config-get",
          label: "Public Config",
          className: "api-method get",
        },
      ],
    },
  ],
};

export default sidebar.apisidebar;
