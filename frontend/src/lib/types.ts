export type UserPublic = {
  id: string;
  email: string;
  full_name: string;
  created_at: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  user: UserPublic;
};

export type CompanySettings = {
  timezone: string;
  locale: string;
  work_days: string[];
};

export type Company = {
  id: string;
  name: string;
  slug: string;
  description: string;
  mission: string;
  industry: string;
  logo_url: string | null;
  settings: CompanySettings | Record<string, unknown>;
  created_by: string;
  created_at: string;
  updated_at: string;
  role: string | null;
};

export type Member = {
  user_id: string;
  full_name: string;
  email: string;
  role: string;
};

export type ActivityEvent = {
  id: string;
  company_id: string;
  agent_id: string | null;
  event_type: string;
  task_id: string | null;
  payload: Record<string, unknown>;
  timestamp: string;
};

export type CompanyOverview = {
  company: Company;
  members: Member[];
  recent_events: ActivityEvent[];
};
