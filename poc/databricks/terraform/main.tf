# Criterion 7 of the proof of concept: how much of the governance the PoC built by API and
# SQL Terraform can own. The same objects as run.py's masking experiment, in their own
# schema: the governed tag, a schema, a table, the classification tag on a column, the
# schema-level mask policy that follows the tag, and the grants. The mask function the
# policy calls has no Terraform resource; poc/databricks/terraform.py creates it with SQL
# between a first, targeted apply and the full one, and records what that costs.

terraform {
  required_providers {
    databricks = {
      source  = "databricks/databricks"
      version = "1.138.0"
    }
  }
}

# Host and token come from DATABRICKS_HOST and DATABRICKS_TOKEN.
provider "databricks" {}

variable "warehouse_id" {
  type        = string
  description = "The SQL warehouse that runs the table's DDL"
}

locals {
  catalog = "workspace"
  schema  = "dpa_tf"
  classes = ["public", "internal", "confidential", "personal"]
  # The users table of the product contract, with each column's classification.
  columns = {
    user_id   = { type = "bigint", class = "internal" }
    email     = { type = "string", class = "personal" }
    full_name = { type = "string", class = "personal" }
    role      = { type = "string", class = "internal" }
  }
}

# The governed tag was created by run.py through the API. Terraform adopts it rather than
# creating a second one.
import {
  to = databricks_tag_policy.class
  id = "class"
}

resource "databricks_tag_policy" "class" {
  tag_key     = "class"
  description = "Data classification (data-platform-architecture)"
  values      = [for c in local.classes : { name = c }]
}

resource "databricks_schema" "poc" {
  catalog_name  = local.catalog
  name          = local.schema
  force_destroy = true
}

resource "databricks_sql_table" "users" {
  catalog_name = local.catalog
  schema_name  = databricks_schema.poc.name
  name         = "users"
  table_type   = "MANAGED"
  warehouse_id = var.warehouse_id

  dynamic "column" {
    for_each = local.columns
    content {
      name = column.key
      type = column.value.type
    }
  }
}

resource "databricks_entity_tag_assignment" "class" {
  for_each    = local.columns
  entity_type = "columns"
  entity_name = "${local.catalog}.${local.schema}.users.${each.key}"
  tag_key     = databricks_tag_policy.class.tag_key
  tag_value   = each.value.class
  depends_on  = [databricks_sql_table.users]
}

# Calls ${local.catalog}.${local.schema}.mask_personal, which only SQL can create.
resource "databricks_policy_info" "mask_personal" {
  name                  = "mask_personal"
  on_securable_type     = "SCHEMA"
  on_securable_fullname = "${local.catalog}.${local.schema}"
  policy_type           = "POLICY_TYPE_COLUMN_MASK"
  for_securable_type    = "TABLE"
  to_principals         = ["account users"]
  match_columns         = [{ condition = "has_tag_value('class', 'personal')", alias = "c" }]
  column_mask = {
    function_name = "${local.catalog}.${local.schema}.mask_personal"
    on_column     = "c"
  }
  depends_on = [databricks_entity_tag_assignment.class]
}

resource "databricks_grants" "schema" {
  schema = "${local.catalog}.${databricks_schema.poc.name}"
  grant {
    principal  = "account users"
    privileges = ["USE_SCHEMA", "SELECT"]
  }
}
