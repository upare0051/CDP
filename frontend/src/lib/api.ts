import axios from 'axios';
import type {
  SourceConnection,
  SourceConnectionCreate,
  DestinationConnection,
  DestinationConnectionCreate,
  SyncJob,
  SyncJobCreate,
  SyncJobSummary,
  SyncRun,
  TableInfo,
  TableSchema,
  TestResult,
  TriggerRunResponse,
  RunStats,
  FieldMapping,
  CustomerListResponse,
  CustomerProfileDetail,
  CustomerEvent,
  CustomerStats,
} from '@/types';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Health
export const checkHealth = () => api.get('/health').then(r => r.data);

// Sources
export const getSources = () => 
  api.get<SourceConnection[]>('/sources').then(r => r.data);

export const getSource = (id: number) => 
  api.get<SourceConnection>(`/sources/${id}`).then(r => r.data);

export const createSource = (data: SourceConnectionCreate) =>
  api.post<SourceConnection>('/sources', data).then(r => r.data);

export const updateSource = (id: number, data: Partial<SourceConnectionCreate>) =>
  api.put<SourceConnection>(`/sources/${id}`, data).then(r => r.data);

export const deleteSource = (id: number) =>
  api.delete(`/sources/${id}`).then(r => r.data);

export const testSource = (id: number) =>
  api.post<TestResult>(`/sources/${id}/test`).then(r => r.data);

export const getSourceSchemas = (id: number) =>
  api.get<string[]>(`/sources/${id}/schemas`).then(r => r.data);

export const getSourceTables = (id: number, schema: string) =>
  api.get<TableInfo[]>(`/sources/${id}/schemas/${schema}/tables`).then(r => r.data);

export const getSourceTableSchema = (id: number, schema: string, table: string) =>
  api.get<TableSchema>(`/sources/${id}/schemas/${schema}/tables/${table}`).then(r => r.data);

// Destinations
export const getDestinations = () =>
  api.get<DestinationConnection[]>('/destinations').then(r => r.data);

export const getDestination = (id: number) =>
  api.get<DestinationConnection>(`/destinations/${id}`).then(r => r.data);

export const createDestination = (data: DestinationConnectionCreate) =>
  api.post<DestinationConnection>('/destinations', data).then(r => r.data);

export const updateDestination = (id: number, data: Partial<DestinationConnectionCreate>) =>
  api.put<DestinationConnection>(`/destinations/${id}`, data).then(r => r.data);

export const deleteDestination = (id: number) =>
  api.delete(`/destinations/${id}`).then(r => r.data);

export const testDestination = (id: number) =>
  api.post<TestResult>(`/destinations/${id}/test`).then(r => r.data);

// Syncs
export const getSyncs = () =>
  api.get<SyncJobSummary[]>('/syncs').then(r => r.data);

export const getSync = (id: number) =>
  api.get<SyncJob>(`/syncs/${id}`).then(r => r.data);

export const createSync = (data: SyncJobCreate) =>
  api.post<SyncJob>('/syncs', data).then(r => r.data);

export const updateSync = (id: number, data: Partial<SyncJobCreate>) =>
  api.put<SyncJob>(`/syncs/${id}`, data).then(r => r.data);

export const deleteSync = (id: number) =>
  api.delete(`/syncs/${id}`).then(r => r.data);

export const updateSyncMappings = (id: number, mappings: Omit<FieldMapping, 'id' | 'sync_job_id' | 'created_at'>[]) =>
  api.put<FieldMapping[]>(`/syncs/${id}/mappings`, mappings).then(r => r.data);

export const triggerSync = (id: number, forceFullRefresh = false) =>
  api.post<TriggerRunResponse>(`/syncs/${id}/trigger`, null, {
    params: { force_full_refresh: forceFullRefresh }
  }).then(r => r.data);

export const pauseSync = (id: number) =>
  api.post(`/syncs/${id}/pause`).then(r => r.data);

export const resumeSync = (id: number) =>
  api.post(`/syncs/${id}/resume`).then(r => r.data);

// Runs
export const getRuns = (jobId?: number, limit = 50) =>
  api.get<SyncRun[]>('/runs', { params: { job_id: jobId, limit } }).then(r => r.data);

export const getRun = (runId: string) =>
  api.get<SyncRun>(`/runs/${runId}`).then(r => r.data);

export const getRunStats = () =>
  api.get<RunStats>('/runs/stats/summary').then(r => r.data);

// Customers (Customer 360)
export interface CustomerListParams {
  search?: string;
  source_id?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  page?: number;
  page_size?: number;
}

export const getCustomers = (params: CustomerListParams = {}) =>
  api.get<CustomerListResponse>('/customers', { params }).then(r => r.data);

export const getCustomer = (id: number) =>
  api.get<CustomerProfileDetail>(`/customers/${id}`).then(r => r.data);

export const getCustomerByExternalId = (externalId: string) =>
  api.get<CustomerProfileDetail>(`/customers/by-external-id/${externalId}`).then(r => r.data);

export const getCustomerTimeline = (id: number, limit = 100, eventType?: string) =>
  api.get<CustomerEvent[]>(`/customers/${id}/timeline`, { 
    params: { limit, event_type: eventType } 
  }).then(r => r.data);

export const getCustomerStats = () =>
  api.get<CustomerStats>('/customers/stats').then(r => r.data);

// ============================================================================
// Segments API
// ============================================================================

export interface FilterCondition {
  field: string;
  operator: string;
  value: any;
  value2?: any;
}

export interface FilterConfig {
  filters: FilterCondition[];
  logic: 'AND' | 'OR';
}

export interface Segment {
  id: number;
  name: string;
  description: string | null;
  filter_config: FilterConfig;
  status: 'draft' | 'active' | 'archived';
  estimated_count: number | null;
  last_count_at: string | null;
  ai_generated: boolean;
  ai_prompt: string | null;
  tags: string[];
  created_at: string;
  updated_at: string;
  created_by: string | null;
}

export interface SegmentCreate {
  name: string;
  description?: string;
  filter_config: FilterConfig;
  tags?: string[];
  ai_generated?: boolean;
  ai_prompt?: string;
}

export interface SegmentUpdate {
  name?: string;
  description?: string;
  filter_config?: FilterConfig;
  status?: string;
  tags?: string[];
}

export interface SegmentListResponse {
  items: Segment[];
  total: number;
  page: number;
  page_size: number;
}

export interface SegmentPreviewResponse {
  count: number;
  sample_customers: Record<string, any>[];
  query_time_ms: number;
}

export interface SegmentField {
  name: string;
  label: string;
  type: 'string' | 'number' | 'date' | 'boolean';
  category: string;
}

export interface SegmentOperator {
  value: string;
  label: string;
}

export interface SegmentSchema {
  fields: SegmentField[];
  operators_by_type: Record<string, SegmentOperator[]>;
}

export interface SegmentFromAIResponse {
  name: string;
  description: string;
  filter_config: FilterConfig;
  estimated_count: number | null;
  segment_id: number | null;
}

// Segment API calls
export const getSegmentSchema = () =>
  api.get<SegmentSchema>('/segments/schema').then(r => r.data);

export const getSegments = (params: {
  page?: number;
  page_size?: number;
  status?: string;
  search?: string;
} = {}) =>
  api.get<SegmentListResponse>('/segments', { params }).then(r => r.data);

export const getSegment = (id: number) =>
  api.get<Segment>(`/segments/${id}`).then(r => r.data);

export const createSegment = (data: SegmentCreate) =>
  api.post<Segment>('/segments', data).then(r => r.data);

export const updateSegment = (id: number, data: SegmentUpdate) =>
  api.patch<Segment>(`/segments/${id}`, data).then(r => r.data);

export const deleteSegment = (id: number) =>
  api.delete(`/segments/${id}`).then(r => r.data);

export const previewSegment = (filter_config: FilterConfig) =>
  api.post<SegmentPreviewResponse>('/segments/preview', { filter_config }).then(r => r.data);

export const refreshSegmentCount = (id: number) =>
  api.post<Segment>(`/segments/${id}/refresh-count`).then(r => r.data);

export const activateSegment = (id: number) =>
  api.post<Segment>(`/segments/${id}/activate`).then(r => r.data);

export const archiveSegment = (id: number) =>
  api.post<Segment>(`/segments/${id}/archive`).then(r => r.data);

export const duplicateSegment = (id: number, new_name?: string) =>
  api.post<Segment>(`/segments/${id}/duplicate`, null, { params: { new_name } }).then(r => r.data);

export const getSegmentCustomers = (id: number, params: { page?: number; page_size?: number } = {}) =>
  api.get(`/segments/${id}/customers`, { params }).then(r => r.data);

export const createSegmentFromAI = (query: string, save = false) =>
  api.post<SegmentFromAIResponse>('/segments/from-ai', { query, save }).then(r => r.data);

// ============================================================================
// Activations API
// ============================================================================

export interface Activation {
  id: number;
  segment_id: number;
  destination_id: number;
  name: string | null;
  frequency: 'manual' | 'hourly' | 'daily' | 'weekly';
  status: 'pending' | 'active' | 'paused' | 'completed' | 'failed';
  field_mappings: any[];
  last_sync_at: string | null;
  last_sync_count: number | null;
  total_synced: number;
  created_at: string;
  updated_at: string;
  segment_name: string | null;
  destination_name: string | null;
  destination_type: string | null;
}

export interface ActivationCreate {
  segment_id: number;
  destination_id: number;
  name?: string;
  frequency?: 'manual' | 'hourly' | 'daily' | 'weekly';
  field_mappings?: any[];
}

export interface ActivationRun {
  id: number;
  run_id: string;
  activation_id: number;
  status: string;
  total_customers: number;
  synced_count: number;
  failed_count: number;
  skipped_count: number;
  started_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
  error_message: string | null;
}

export interface DashboardStats {
  total_customers: number;
  total_segments: number;
  active_segments: number;
  total_activations: number;
  active_activations: number;
  customers_added_today: number;
  customers_added_week: number;
  segments_created_week: number;
  syncs_today: number;
  top_segments: {
    id: number;
    name: string;
    count: number;
    status: string;
    ai_generated: boolean;
  }[];
  recent_activations: {
    id: number;
    name: string;
    segment_name: string | null;
    destination_name: string | null;
    last_sync_at: string | null;
    last_sync_count: number | null;
    status: string;
  }[];
}

// Activations API calls
export const getDashboardStats = () =>
  api.get<DashboardStats>('/activations/dashboard').then(r => r.data);

export const getActivations = (params: {
  segment_id?: number;
  destination_id?: number;
  status?: string;
} = {}) =>
  api.get<{ items: Activation[]; total: number }>('/activations', { params }).then(r => r.data);

export const getActivation = (id: number) =>
  api.get<Activation>(`/activations/${id}`).then(r => r.data);

export const createActivation = (data: ActivationCreate) =>
  api.post<Activation>('/activations', data).then(r => r.data);

export const updateActivation = (id: number, data: Partial<ActivationCreate> & { status?: string }) =>
  api.patch<Activation>(`/activations/${id}`, data).then(r => r.data);

export const deleteActivation = (id: number) =>
  api.delete(`/activations/${id}`).then(r => r.data);

export const triggerActivation = (id: number) =>
  api.post<{ run_id: string; status: string; message: string }>(`/activations/${id}/trigger`).then(r => r.data);

export const getActivationRuns = (id: number, limit = 10) =>
  api.get<ActivationRun[]>(`/activations/${id}/runs`, { params: { limit } }).then(r => r.data);

export const pauseActivation = (id: number) =>
  api.post<Activation>(`/activations/${id}/pause`).then(r => r.data);

export const resumeActivation = (id: number) =>
  api.post<Activation>(`/activations/${id}/resume`).then(r => r.data);

// Segment Export
export const exportSegment = (segmentId: number, includedFields: string[] = [], includeAttributes = true) =>
  api.post(`/activations/segments/${segmentId}/export`, 
    { included_fields: includedFields, include_attributes: includeAttributes },
    { responseType: 'blob' }
  ).then(r => r.data);

export const getSegmentExports = (segmentId: number, limit = 10) =>
  api.get(`/activations/segments/${segmentId}/exports`, { params: { limit } }).then(r => r.data);

// ============================================================================
// Writeback API
// ============================================================================

export interface WritebackJob {
  id: number;
  name: string;
  description: string | null;
  source_type: 'ai_customer_insights';
  source_filters: Record<string, any>;
  target_type: 'customer_attributes';
  attribute_name: string;
  attribute_type: 'string' | 'number' | 'boolean' | 'date' | 'json';
  value_mapping: { mode: 'static' | 'field'; value?: string; field?: string };
  status: 'draft' | 'active' | 'archived';
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface WritebackRun {
  id: number;
  job_id: number;
  run_type: 'preview' | 'apply';
  status: 'running' | 'completed' | 'failed';
  total_candidates: number;
  total_updates: number;
  total_inserts: number;
  total_failed: number;
  sample_preview: Record<string, any>[] | null;
  error_message: string | null;
  started_at: string;
  completed_at: string | null;
  created_at: string;
}

export const getWritebackJobs = () =>
  api.get<WritebackJob[]>('/writeback/jobs').then(r => r.data);

export const createWritebackJob = (data: Omit<WritebackJob, 'id' | 'status' | 'created_at' | 'updated_at'>) =>
  api.post<WritebackJob>('/writeback/jobs', data).then(r => r.data);

export const previewWritebackJob = (jobId: number, limit = 20) =>
  api.post<{ total_candidates: number; sample_rows: Record<string, any>[]; attribute_name: string; attribute_type: string }>(
    `/writeback/jobs/${jobId}/preview`,
    null,
    { params: { limit } }
  ).then(r => r.data);

export const applyWritebackJob = (jobId: number) =>
  api.post<{ run_id: number; status: string; total_candidates: number; total_updates: number; total_inserts: number; total_failed: number }>(
    `/writeback/jobs/${jobId}/apply`
  ).then(r => r.data);

export const getWritebackRuns = (jobId: number, limit = 20) =>
  api.get<WritebackRun[]>(`/writeback/jobs/${jobId}/runs`, { params: { limit } }).then(r => r.data);

// ============================================================================
// Data Explorer API
// ============================================================================

export interface ExplorerColumn {
  name: string;
  type: string;
}

export interface ExplorerTable {
  catalog: string;
  schema: string;
  table: string;
  table_reference: string;
  row_count: number | null;
  columns: ExplorerColumn[];
}

export interface ExplorerSchemaResponse {
  database: string;
  tables: ExplorerTable[];
}

export interface ExplorerErdResponse {
  nodes: { table: string }[];
  edges: { from_table: string; from_column: string; to_table: string; to_column: string }[];
}

export interface ExplorerQueryResponse {
  columns: string[];
  rows: any[][];
  row_count: number;
  truncated: boolean;
}

export interface ExplorerTeamViewCard {
  team: string;
  title: string;
  value: number;
  metric_key: string;
}

export interface ExplorerTeamViewsResponse {
  cards: ExplorerTeamViewCard[];
  cs_priority_sample: {
    customer_id: number;
    external_id: string;
    churn_level: string | null;
    churn_score: number | null;
    action_bucket: string;
  }[];
  da_goal_breakdown: {
    goal: string;
    recommendation_count: number;
  }[];
}

export const getExplorerSchema = () =>
  api.get<ExplorerSchemaResponse>('/explorer/schema').then(r => r.data);

export const getExplorerErd = () =>
  api.get<ExplorerErdResponse>('/explorer/erd').then(r => r.data);

export const runExplorerQuery = (sql: string, limit = 500) =>
  api.post<ExplorerQueryResponse>('/explorer/query', { sql, limit }).then(r => r.data);

export const getExplorerTeamViews = () =>
  api.get<ExplorerTeamViewsResponse>('/explorer/team-views').then(r => r.data);

// ============================================================================
// C360 (Redshift live)
// ============================================================================

export interface C360SchemaResponse {
  allowlisted_tables: string[];
  schema: {
    database: string;
    tables: {
      schema: string;
      table: string;
      table_reference: string;
      columns: { name: string; type: string }[];
    }[];
  };
}

export const getC360Schema = () =>
  api.get<C360SchemaResponse>('/c360/schema').then((r) => r.data);

export interface C360ChatResponse {
  answer: string;
  sql: string | null;
  sql_results: Record<string, any>[] | null;
  pii_redacted: boolean;
  cache_hit: boolean;
}

export const c360Chat = (
  question: string,
  history: { role: string; content: string }[] = []
) => api.post<C360ChatResponse>('/c360/chat', { question, history }).then((r) => r.data);

// ============================================================================
// Public Landing API
// ============================================================================

export interface LeadCaptureRequest {
  email: string;
  full_name?: string;
  company?: string;
  use_case?: string;
  primary_use_case?: string;
  company_size?: string;
  stack?: string;
  consent_follow_up?: boolean;
  request_demo_call?: boolean;
  intent_choice?: string;
  source?: string;
}

export interface LeadCaptureResponse {
  id: number;
  email: string;
  full_name: string | null;
  company: string | null;
  use_case: string | null;
  source: string;
  created_at: string;
  demo_url: string;
  message: string;
}

export const captureLead = (payload: LeadCaptureRequest) =>
  api.post<LeadCaptureResponse>('/public/lead-capture', payload).then(r => r.data);

export interface VisitCaptureRequest {
  session_id: string;
  page_path?: string;
  referrer?: string;
  source?: string;
}

export const captureVisit = (payload: VisitCaptureRequest) =>
  api.post('/public/visit', payload).then(r => r.data);

// ============================================================================
// Admin Analytics API
// ============================================================================

export interface AdminDailyMetric {
  day: string;
  visits: number;
  leads: number;
}

export interface AdminAnalyticsSummary {
  days: number;
  visitors_today: number;
  visitors_last_7d: number;
  leads_today: number;
  leads_last_7d: number;
  lead_conversion_rate_last_7d: number;
  leads_by_industry_last_7d: { industry: string; leads: number }[];
  recent_daily_metrics: AdminDailyMetric[];
}

export interface AdminLeadItem {
  id: number;
  email: string;
  full_name: string | null;
  company: string | null;
  use_case: string | null;
  source: string;
  created_at: string;
}

export interface AdminLeadListResponse {
  items: AdminLeadItem[];
  total: number;
  page: number;
  page_size: number;
}

const withAdminHeaders = (adminKey: string) => ({
  headers: { 'x-admin-key': adminKey },
});

export const getAdminAnalyticsSummary = (adminKey: string, days = 14) =>
  api
    .get<AdminAnalyticsSummary>('/admin/analytics/summary', {
      params: { days },
      ...withAdminHeaders(adminKey),
    })
    .then((r) => r.data);

export const getAdminLeads = (adminKey: string, params: { page?: number; page_size?: number; search?: string } = {}) =>
  api
    .get<AdminLeadListResponse>('/admin/analytics/leads', {
      params,
      ...withAdminHeaders(adminKey),
    })
    .then((r) => r.data);

export const exportAdminLeadsCsv = (adminKey: string) =>
  api
    .get('/admin/analytics/leads/export.csv', {
      responseType: 'blob',
      ...withAdminHeaders(adminKey),
    })
    .then((r) => r.data as Blob);

export default api;
