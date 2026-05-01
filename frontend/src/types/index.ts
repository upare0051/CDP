// API Types

export type SourceType = 'redshift' | 'duckdb';
export type DestinationType = 'braze' | 'attentive';
export type SyncMode = 'full_refresh' | 'incremental';
export type SyncStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
export type ScheduleType = 'manual' | 'cron';

export interface SourceConnection {
  id: number;
  name: string;
  source_type: SourceType;
  host?: string;
  port?: number;
  database?: string;
  username?: string;
  duckdb_path?: string;
  extra_config?: Record<string, unknown>;
  is_active: boolean;
  last_tested_at?: string;
  last_test_success?: boolean;
  created_at: string;
  updated_at: string;
}

export interface SourceConnectionCreate {
  name: string;
  source_type: SourceType;
  host?: string;
  port?: number;
  database?: string;
  username?: string;
  password?: string;
  duckdb_path?: string;
  extra_config?: Record<string, unknown>;
}

export interface DestinationConnection {
  id: number;
  name: string;
  destination_type: DestinationType;
  api_endpoint?: string;
  braze_app_id?: string;
  attentive_api_url?: string;
  rate_limit_per_second?: number;
  batch_size?: number;
  extra_config?: Record<string, unknown>;
  is_active: boolean;
  last_tested_at?: string;
  last_test_success?: boolean;
  created_at: string;
  updated_at: string;
  api_key_masked?: string;
}

export interface DestinationConnectionCreate {
  name: string;
  destination_type: DestinationType;
  api_key: string;
  api_endpoint?: string;
  braze_app_id?: string;
  attentive_api_url?: string;
  rate_limit_per_second?: number;
  batch_size?: number;
}

export interface FieldMapping {
  id?: number;
  sync_job_id?: number;
  source_field: string;
  source_field_type?: string;
  destination_field: string;
  transformation?: string;
  is_sync_key: boolean;
  is_required: boolean;
  created_at?: string;
}

export interface SyncJob {
  id: number;
  name: string;
  description?: string;
  source_connection_id: number;
  destination_connection_id: number;
  source_schema: string;
  source_table: string;
  source_query?: string;
  sync_mode: SyncMode;
  sync_key: string;
  incremental_column?: string;
  last_checkpoint_value?: string;
  schedule_type: ScheduleType;
  cron_expression?: string;
  airflow_dag_id?: string;
  is_active: boolean;
  is_paused: boolean;
  source_schema_hash?: string;
  last_schema_check_at?: string;
  created_at: string;
  updated_at: string;
  field_mappings: FieldMapping[];
  source_connection_name?: string;
  destination_connection_name?: string;
  last_run_status?: SyncStatus;
  last_run_at?: string;
}

export interface SyncJobCreate {
  name: string;
  description?: string;
  source_connection_id: number;
  destination_connection_id: number;
  source_schema: string;
  source_table: string;
  source_query?: string;
  sync_mode: SyncMode;
  sync_key: string;
  incremental_column?: string;
  schedule_type: ScheduleType;
  cron_expression?: string;
  field_mappings: Omit<FieldMapping, 'id' | 'sync_job_id' | 'created_at'>[];
}

export interface SyncJobSummary {
  id: number;
  name: string;
  source_connection_name: string;
  destination_connection_name: string;
  sync_mode: SyncMode;
  schedule_type: ScheduleType;
  is_active: boolean;
  is_paused: boolean;
  last_run_status?: SyncStatus;
  last_run_at?: string;
  total_rows_synced: number;
}

export interface SyncRun {
  id: number;
  sync_job_id: number;
  run_id: string;
  airflow_run_id?: string;
  status: SyncStatus;
  started_at?: string;
  completed_at?: string;
  duration_seconds?: number;
  rows_read: number;
  rows_synced: number;
  rows_failed: number;
  rows_skipped: number;
  checkpoint_value?: string;
  new_checkpoint_value?: string;
  error_message?: string;
  retry_count: number;
  created_at: string;
  updated_at: string;
  sync_job_name?: string;
  logs?: string;
  error_details?: Record<string, unknown>;
}

export interface TableInfo {
  schema_name: string;
  table_name: string;
  row_count?: number;
}

export interface ColumnInfo {
  column_name: string;
  data_type: string;
  is_nullable: boolean;
  is_primary_key: boolean;
}

export interface TableSchema {
  schema_name: string;
  table_name: string;
  columns: ColumnInfo[];
  row_count?: number;
}

export interface TestResult {
  success: boolean;
  message: string;
  tables_found?: number;
  error?: string;
}

export interface TriggerRunResponse {
  run_id: string;
  status: SyncStatus;
  message: string;
}

export interface RunStats {
  total_runs: number;
  runs_last_24h: number;
  status_breakdown: Record<string, number>;
  total_rows_synced: number;
  total_rows_failed: number;
  success_rate: number;
}

// Customer 360 Types

export interface CustomerAttribute {
  id: number;
  customer_id: number;
  attribute_name: string;
  attribute_value?: string;
  attribute_type: string;
  source_connection_id?: number;
  source_field?: string;
  source_name?: string;
  created_at: string;
  updated_at: string;
}

export interface CustomerEvent {
  id: number;
  customer_id: number;
  event_type: string;
  event_category: string;
  title?: string;
  description?: string;
  event_data?: Record<string, unknown>;
  source_connection_id?: number;
  destination_connection_id?: number;
  sync_run_id?: string;
  occurred_at: string;
  source_name?: string;
  destination_name?: string;
}

export interface CustomerIdentity {
  id: number;
  identity_type: string;
  identity_value: string;
  source_connection_id?: number;
  source_name?: string;
  is_primary: boolean;
  verified: boolean;
  created_at: string;
}

export interface CustomerProfile {
  id: number;
  external_id: string;
  email?: string;
  phone?: string;
  first_name?: string;
  last_name?: string;
  full_name: string;
  source_count: number;
  first_seen_at?: string;
  last_seen_at?: string;
  last_synced_at?: string;
  lifetime_value?: number;
  total_orders?: number;
  city?: string;
  country?: string;
}

export interface CustomerProfileDetail extends CustomerProfile {
  attributes: CustomerAttribute[];
  recent_events: CustomerEvent[];
  identities: CustomerIdentity[];
  created_at: string;
  updated_at: string;
}

export interface CustomerListResponse {
  customers: CustomerProfile[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface CustomerStats {
  total_customers: number;
  customers_added_today: number;
  customers_added_this_week: number;
  customers_synced_today: number;
  avg_attributes_per_customer: number;
  top_sources: { source_name: string; customer_count: number }[];
}
