export interface AgentQueueMessage {
  kind?: "agent" | "music" | "backup";
  runId?: string;
  jobId?: string;
}

export interface CloudUser {
  id: string;
  username: string;
  role: "admin" | "user";
}

export interface Env {
  DB: D1Database;
  AI: Ai;
  ASSETS: Fetcher;
  AGENT_QUEUE: Queue<AgentQueueMessage>;
  EVENT_HUB: DurableObjectNamespace;
  VECTORIZE: VectorizeIndex;
  /** Optional until R2 is enabled for this Cloudflare account. */
  OBJECTS?: R2Bucket;
  AI_MODEL: string;
  IMAGE_MODEL?: string;
  EMBEDDING_MODEL?: string;
  GITHUB_OWNER: string;
  GITHUB_REPO: string;
  GITHUB_TOKEN: string;
  RUNNER_CALLBACK_SECRET: string;
  CLOUD_BOOTSTRAP_TOKEN: string;
  AUTH_ENCRYPTION_KEY: string;
  OAUTH_GOOGLE_CLIENT_ID?: string;
  OAUTH_GOOGLE_CLIENT_SECRET?: string;
  OAUTH_GITHUB_CLIENT_ID?: string;
  OAUTH_GITHUB_CLIENT_SECRET?: string;
  PUBLIC_ORIGIN?: string;
  SESSION_HOURS?: string;
  AGENT_DAILY_LIMIT?: string;
}

export interface RequestContext {
  request: Request;
  env: Env;
  execution: ExecutionContext;
  user: CloudUser | null;
}

export interface AgentRunRow {
  id: string;
  user_id: string;
  task: string;
  mode: string;
  status: string;
  answer: string | null;
  pull_request_url: string | null;
  branch_name: string | null;
  error_detail: string | null;
  trace_json: string;
  attachments_json: string;
  workspace_id?: string | null;
  workflow_json?: string;
  project_plan_json?: string | null;
  attempt_count?: number;
  cancel_requested?: number;
  created_at: number;
  updated_at: number;
  started_at: number | null;
  completed_at: number | null;
}
