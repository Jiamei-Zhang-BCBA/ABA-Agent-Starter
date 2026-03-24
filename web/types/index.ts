// Auth
export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface User {
  id: string;
  tenant_id: string;
  role: "org_admin" | "bcba" | "teacher" | "parent";
  name: string;
  email: string;
}

// Registration
export interface RegisterRequest {
  org_name: string;
  admin_name: string;
  admin_email: string;
  admin_password: string;
  plan_name?: string;
}

export interface RegisterResponse {
  tenant_id: string;
  user_id: string;
  email: string;
  access_token: string;
  refresh_token: string;
}

// Invitation
export interface InvitationCreateRequest {
  email: string;
  role: "bcba" | "teacher" | "parent";
}

export interface InvitationResponse {
  id: string;
  email: string;
  role: string;
  token: string;
  expires_at: string;
}

export interface InvitationAcceptRequest {
  token: string;
  name: string;
  password: string;
}

// Password Reset
export interface PasswordResetRequest {
  email: string;
}

export interface PasswordResetConfirm {
  token: string;
  new_password: string;
}

// Users
export interface UserDetail {
  id: string;
  tenant_id: string;
  role: string;
  name: string;
  email: string;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
}

export interface UserListResponse {
  users: UserDetail[];
  total: number;
}

export interface UserUpdateRequest {
  name?: string;
  role?: string;
  is_active?: boolean;
}

// Features
export interface FormField {
  name: string;
  label: string;
  type: "text" | "number" | "textarea" | "file" | "select_client" | "select_staff";
  required: boolean;
  accept?: string[];
  options?: { value: string; label: string }[];
}

export interface Feature {
  id: string;
  display_name: string;
  description: string;
  icon: string;
  category: string;
  form_schema: { fields: FormField[] };
  output_template: string;
}

export interface FeatureListResponse {
  features: Feature[];
}

// Jobs
export interface Job {
  id: string;
  tenant_id: string;
  user_id: string;
  client_id: string | null;
  feature_id: string;
  status: string;
  created_at: string;
  completed_at: string | null;
}

export interface JobDetail extends Job {
  form_data_json: Record<string, unknown>;
  output_content: string | null;
  error_message: string | null;
  input_tokens: number;
  output_tokens: number;
}

export interface JobListResponse {
  jobs: Job[];
  total: number;
}

// Clients
export interface Client {
  id: string;
  tenant_id: string;
  code_name: string;
  display_alias: string;
  status: string;
  created_at: string;
}

export interface Staff {
  id: string;
  name: string;
  role: string;
}

// Reviews
export interface Review {
  id: string;
  job_id: string;
  reviewer_id: string | null;
  output_content: string;
  modified_content: string | null;
  status: string;
  comments: string | null;
  created_at: string;
  reviewed_at: string | null;
}
