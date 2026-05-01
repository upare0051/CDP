variable "tenant_id" {
  description = "Internal tenant identifier"
  type        = string
}

variable "tenant_slug" {
  description = "Tenant slug used for hostnames and resource prefixes"
  type        = string
}

variable "project_id" {
  description = "GCP project id for tenant deployment"
  type        = string
}

variable "region" {
  description = "GCP region for deployment"
  type        = string
  default     = "us-central1"
}

variable "domain_root" {
  description = "Base domain for tenant URLs"
  type        = string
  default     = "activationos.local"
}

variable "ai_provider" {
  description = "AI provider gateway"
  type        = string
  default     = "ollama"
}

variable "ai_model" {
  description = "Default model for tenant"
  type        = string
  default     = "meta-llama/llama-3.1-8b-instruct"
}

variable "ai_model_fast" {
  description = "Fast model for tenant"
  type        = string
  default     = "mistralai/mistral-7b-instruct"
}

variable "ai_model_smart" {
  description = "Higher-quality model for tenant"
  type        = string
  default     = "anthropic/claude-3-haiku-20240307"
}
