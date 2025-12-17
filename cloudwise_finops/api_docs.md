# API Documentation for CloudWise FinOps Agency

## Research Summary
- **Total capabilities needed**: 24 tools across 5 agents
- **MCP coverage**: 75% covered by MCP servers
- **Built-in tools applicable**: None directly (web search not needed for FinOps data)
- **Custom tools required**: 6 tools (anomaly detection algorithms, optimization logic, policy validation)
- **Research date**: 2025-12-17

### MCP Coverage Analysis
**Covered by MCP (18/24 tools):**
- AWS cost data retrieval (7 MCP tools)
- GCP billing data access (5 MCP tools via BigQuery)
- Azure cost management (3 MCP tools)
- Data caching/storage (3 MCP tools via SQLite/Postgres)

**Requires Custom Implementation (6/24 tools):**
- Anomaly detection algorithms (baseline calculation, spike detection, classification)
- Optimization recommendations (rightsizing, RI analysis, arbitrage calculations)
- Policy validation logic

---

## MCP Servers Available

### 1. AWS Cost Explorer MCP Server (Official AWS Labs)

**Package**: `awslabs.cost-explorer-mcp-server`

**Installation**:
```bash
uvx awslabs.cost-explorer-mcp-server@latest
```

**Tools Provided**:
- `get_today_date` - Retrieve current date/month for queries
- `get_dimension_values` - Fetch available dimension values (SERVICE, REGION, LINKED_ACCOUNT, etc.)
- `get_tag_values` - Get available tag values for filtering
- `get_cost_and_usage` - Query cost and usage data with filtering and grouping
- `get_cost_and_usage_comparisons` - Compare costs between two time periods
- `get_cost_comparison_drivers` - Identify top 10 cost change drivers
- `get_cost_forecast` - Generate cost forecasts with 80% or 95% confidence intervals

**Configuration**:
```json
{
  "mcpServers": {
    "aws-cost-explorer": {
      "command": "uvx",
      "args": ["awslabs.cost-explorer-mcp-server@latest"],
      "env": {
        "AWS_PROFILE": "default",
        "AWS_REGION": "us-east-1",
        "FASTMCP_LOG_LEVEL": "ERROR"
      }
    }
  }
}
```

**Authentication**: Uses AWS credentials from local AWS CLI configuration

**IAM Permissions Required**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ce:GetCostAndUsage",
        "ce:GetDimensionValues",
        "ce:GetTags",
        "ce:GetCostForecast",
        "ce:GetCostAndUsageComparisons",
        "ce:GetCostComparisonDrivers"
      ],
      "Resource": "*"
    }
  ]
}
```

**Rate Limits**: No AWS-side rate limits, but each API call costs $0.01

**Pricing Note**: AWS Cost Explorer API charges $0.01 per paginated request. Complex queries may generate multiple requests.

**Use Cases in CloudWise**:
- Cloud Connector Agent: Fetch AWS cost data
- Anomaly Detector Agent: Get historical data for baseline calculations
- Reporter Agent: Generate cost reports and forecasts

---

### 2. AWS Billing and Cost Management MCP Server (Official AWS)

**Package**: `billing-cost-management-mcp-server` (announced at AWS re:Invent 2025)

**Description**: Comprehensive MCP server that bridges AI assistants with multiple AWS cost services:
- AWS Cost Explorer
- AWS Cost Optimization Hub
- AWS Compute Optimizer
- AWS Savings Plans
- AWS Budgets
- Amazon S3 Storage Lens
- AWS Cost Anomaly Detection

**Tools Provided**: Broader than Cost Explorer alone, includes:
- Budget monitoring and alerts
- Savings Plans recommendations
- Compute optimization suggestions
- S3 storage cost analysis
- Native anomaly detection results

**Authentication**: Same as Cost Explorer (AWS credentials via CLI)

**Configuration**: Similar to Cost Explorer MCP server with extended capabilities

**Use Cases in CloudWise**:
- Optimizer Agent: Get RI/Savings Plans recommendations
- Policy Engine Agent: Check budget status and constraints
- Anomaly Detector Agent: Leverage AWS native anomaly detection

**Note**: This is the more comprehensive option if you need broader AWS cost management features beyond basic cost data.

---

### 3. Community AWS FinOps MCP Server

**Repository**: `github.com/ravikiranvm/aws-finops-mcp-server`

**Features**:
- Detailed cost analysis with tags and time ranges
- Automated FinOps audit (stopped EC2 instances, unattached EBS volumes, unassociated Elastic IPs)
- Budget monitoring

**Use Cases**: Alternative to official AWS MCP if you prefer community-maintained tools with built-in waste detection

---

### 4. Google Cloud BigQuery MCP Server (Official Google)

**Package**: Google MCP Toolbox for Databases (BigQuery component)

**Installation**:
```bash
# Install MCP Toolbox
npm install -g @googleapis/mcp-toolbox

# Or use directly
./toolbox --prebuilt bigquery --stdio
```

**Tools Provided**:
- `list_dataset_ids` - Fetch BigQuery dataset IDs in a GCP project
- `get_dataset_info` - Fetch metadata about a BigQuery dataset
- `list_table_ids` - Fetch table IDs in a BigQuery dataset
- `get_table_info` - Fetch metadata about a BigQuery table
- `execute_sql` - Run SQL queries in BigQuery and fetch results

**Configuration**:
```json
{
  "mcpServers": {
    "bigquery": {
      "command": "./PATH/TO/toolbox",
      "args": ["--prebuilt", "bigquery", "--stdio"],
      "env": {
        "BIGQUERY_PROJECT": "your-project-id"
      }
    }
  }
}
```

**Authentication**: Uses Google Cloud Application Default Credentials (ADC)

**Required Permissions**:
- `bigquery.datasets.get`
- `bigquery.tables.get`
- `bigquery.jobs.create`
- `bigquery.jobs.get`

**Rate Limits**:
- Standard BigQuery API quota: 100 concurrent queries per project
- Cost: Based on BigQuery pricing (first 1 TB of query data processed per month is free)

**Use Cases in CloudWise**:
- Cloud Connector Agent: Query GCP billing export data from BigQuery
- Reporter Agent: Generate GCP cost reports via SQL queries

**Prerequisites for GCP Billing**:
1. Enable Cloud Billing data export to BigQuery (see section below)
2. Ensure billing export dataset exists
3. Grant service account access to billing dataset

---

### 5. Community GCP MCP Server

**Repository**: `github.com/eniayomi/gcp-mcp`

**Features**:
- `get-billing-info` - Get billing information for the current project
- General GCP resource queries
- BigQuery dataset and table browsing

**Use Cases**: Lighter-weight alternative for basic GCP cost queries

---

### 6. Azure Billing MCP Server

**Package**: `mcp-azure-billing` (PyPI)

**Installation**:
```bash
pip install mcp-azure-billing
```

**Tools Provided**:
- Cost Analysis: Analyze Azure costs with various timeframes and granularity
- Budget Management: View existing budget information
- Usage Details: Get detailed resource usage information
- Subscription Information: Retrieve subscription details
- Price Sheet: Access pricing information for Azure services

**Configuration**:
```json
{
  "mcpServers": {
    "azure-billing": {
      "command": "python",
      "args": ["-m", "mcp_azure_billing"],
      "env": {
        "AZURE_TENANT_ID": "your-tenant-id",
        "AZURE_CLIENT_ID": "your-client-id",
        "AZURE_CLIENT_SECRET": "your-client-secret",
        "AZURE_SUBSCRIPTION_ID": "your-subscription-id"
      }
    }
  }
}
```

**Authentication**: Azure Service Principal with Cost Management Reader role

**Required Permissions**: `Cost Management Reader` role at subscription scope

**Rate Limits**:
- 4 calls per scope per minute (programmatic tokens)
- 60-second timeout per request
- ClientType filter: 2000 calls/minute if ClientType provided in headers

**Use Cases in CloudWise**:
- Cloud Connector Agent: Fetch Azure cost data
- Reporter Agent: Generate Azure cost reports

---

### 7. Azure Pricing MCP Server

**Repository**: `github.com/charris-msft/azure-pricing-mcp`

**Package**: `@azure/mcp` or community alternatives

**Features**:
- Azure Price Search with flexible filtering
- Service comparison across regions and SKUs
- Cost estimation based on usage patterns
- Savings Plan information
- Multi-currency support

**Authentication**: Uses Azure Retail Prices API (no Azure account required for pricing queries)

**Use Cases in CloudWise**:
- Optimizer Agent: Compare pricing across Azure regions
- Reporter Agent: Calculate cost estimates for resource recommendations

---

### 8. Database MCP Servers (for Caching)

#### SQLite MCP Server

**Package**: `@modelcontextprotocol/server-sqlite`

**Installation**:
```bash
npx @modelcontextprotocol/server-sqlite /path/to/database.db
```

**Tools Provided**:
- Execute SQL queries
- Read database schema
- Query table metadata

**Use Cases in CloudWise**:
- Cloud Connector Agent: Cache normalized cost snapshots locally
- Anomaly Detector Agent: Store baseline calculations and historical patterns

#### PostgreSQL MCP Server

**Package**: `@modelcontextprotocol/server-postgres`

**Installation**:
```bash
npx @modelcontextprotocol/server-postgres <connection-string>
```

**Configuration**:
```json
{
  "mcpServers": {
    "postgres": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-postgres", "postgresql://user:pass@localhost:5432/finops"],
      "env": {}
    }
  }
}
```

**Use Cases in CloudWise**:
- Larger deployments needing centralized cost data storage
- Multi-agent coordination with shared data access

---

### 9. Filesystem MCP Server

**Package**: `@modelcontextprotocol/server-filesystem`

**Installation**:
```bash
npx @modelcontextprotocol/server-filesystem /path/to/allowed/directory
```

**Tools Provided**:
- read_file - Read file contents
- write_file - Create or update files
- list_directory - List directory contents
- move_file - Move or rename files
- delete_file - Delete files

**Security**: Operates only within specified allowed directories

**Use Cases in CloudWise**:
- Reporter Agent: Save generated cost reports to disk
- Cloud Connector Agent: Cache API responses to files

---

## Traditional APIs (No MCP Server)

### AWS Savings Plans API

**Service**: AWS Savings Plans (part of AWS Cost Management)

**Access Method**: AWS SDK (Boto3 for Python)

**Key Operations**:
- `describe_savings_plans` - List active Savings Plans
- `describe_savings_plans_offering_rates` - Get current offering rates
- `describe_savings_plans_offerings` - Get available offerings

**Authentication**: AWS IAM (same as Cost Explorer)

**Required Permissions**:
```json
{
  "Effect": "Allow",
  "Action": [
    "savingsplans:DescribeSavingsPlans",
    "savingsplans:DescribeSavingsPlansOfferings",
    "savingsplans:DescribeSavingsPlansOfferingRates"
  ],
  "Resource": "*"
}
```

**Rate Limits**: Standard AWS API limits (typically 100 requests/second)

**Python Example**:
```python
import boto3

client = boto3.client('savingsplans', region_name='us-east-1')
response = client.describe_savings_plans_offerings(
    filters=[
        {'name': 'region', 'values': ['us-east-1']},
        {'name': 'instanceFamily', 'values': ['m5']}
    ]
)
```

**Use Cases in CloudWise**:
- Optimizer Agent: Calculate potential savings from Savings Plans
- Policy Engine Agent: Validate Savings Plans compliance

---

### AWS EC2 Spot Pricing API

**Service**: Amazon EC2

**Access Method**: AWS SDK (Boto3 for Python)

**Key Operations**:
- `describe_spot_price_history` - Get historical spot prices
- `describe_spot_instance_requests` - Check spot request status

**Authentication**: AWS IAM credentials

**Required Permissions**:
```json
{
  "Effect": "Allow",
  "Action": [
    "ec2:DescribeSpotPriceHistory",
    "ec2:DescribeSpotInstanceRequests"
  ],
  "Resource": "*"
}
```

**Rate Limits**: ~100 requests/second (varies by region, implement exponential backoff)

**Python Example**:
```python
import boto3

ec2 = boto3.client('ec2', region_name='us-east-1')
response = ec2.describe_spot_price_history(
    InstanceTypes=['m5.large'],
    ProductDescriptions=['Linux/UNIX'],
    MaxResults=100
)
```

**Use Cases in CloudWise**:
- Optimizer Agent: Recommend spot instance usage
- Reporter Agent: Include spot pricing in cost forecasts

---

### AWS Reserved Instances API

**Service**: Amazon EC2

**Access Method**: AWS SDK (Boto3 for Python)

**Key Operations**:
- `describe_reserved_instances` - List active RIs
- `describe_reserved_instances_offerings` - Get available RI offerings
- `describe_reserved_instances_modifications` - Track RI modifications

**Authentication**: AWS IAM credentials

**Required Permissions**:
```json
{
  "Effect": "Allow",
  "Action": [
    "ec2:DescribeReservedInstances",
    "ec2:DescribeReservedInstancesOfferings",
    "ec2:DescribeReservedInstancesModifications"
  ],
  "Resource": "*"
}
```

**Rate Limits**: Standard EC2 API limits

**Use Cases in CloudWise**:
- Optimizer Agent: Calculate RI utilization and recommendations
- Reporter Agent: Include RI coverage in reports

---

### GCP Compute Engine Pricing API

**Service**: Google Cloud Compute Engine

**Access Method**: Google Cloud Client Libraries

**Key Operations**:
- List machine type pricing
- Get committed use discount details
- Query preemptible instance pricing

**Authentication**: Google Cloud Service Account with `compute.viewer` role

**Rate Limits**: 2000 queries per 100 seconds per project

**Python Example**:
```python
from google.cloud import compute_v1

client = compute_v1.MachineTypesClient()
request = compute_v1.ListMachineTypesRequest(
    project="your-project-id",
    zone="us-central1-a"
)
response = client.list(request=request)
```

**Use Cases in CloudWise**:
- Optimizer Agent: Calculate rightsizing savings for GCP
- Reporter Agent: Estimate GCP compute costs

---

### Azure Reserved VM Instances API

**Service**: Azure Compute

**Access Method**: Azure SDK for Python or REST API

**Base URL**: `https://management.azure.com`

**Key Endpoints**:
- `GET /subscriptions/{subscriptionId}/providers/Microsoft.Compute/virtualMachines` - List VMs
- `GET /providers/Microsoft.Capacity/catalogs` - Get reservation catalog
- `GET /providers/Microsoft.Capacity/reservationOrders` - List reservations

**Authentication**: Azure Service Principal with appropriate RBAC roles

**Required Roles**:
- `Reader` - For listing resources
- `Reservation Reader` - For viewing reservations

**Rate Limits**:
- Read operations: 15,000 requests per hour per subscription
- Write operations: 1,200 requests per hour per subscription

**Python Example**:
```python
from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient

credential = DefaultAzureCredential()
compute_client = ComputeManagementClient(credential, subscription_id)

for vm in compute_client.virtual_machines.list_all():
    print(f"{vm.name}: {vm.hardware_profile.vm_size}")
```

**Use Cases in CloudWise**:
- Optimizer Agent: Analyze Azure RI utilization
- Reporter Agent: Include Azure RI coverage

---

## Required API Keys Summary

### 1. OPENAI_API_KEY (Always Required)

**Purpose**: Powers all Agency Swarm agents via OpenAI API

**How to Obtain**:
1. Visit https://platform.openai.com/api-keys
2. Sign up or log in to your OpenAI account
3. Click "Create new secret key"
4. Name your key (e.g., "CloudWise FinOps Agency")
5. Copy the key immediately (shown only once)
6. Add billing information: https://platform.openai.com/account/billing
   - Minimum $5 recommended for testing
   - Production usage: $50-100+ depending on query volume

**Expected Usage for CloudWise**:
- ~$0.50-2.00 per complex cost analysis query
- Budget $100-500/month for active multi-cloud monitoring

**Rate Limits**:
- Tier 1 (new accounts): 500 requests/minute, 10,000 tokens/minute
- Tier 4 ($250+ spent): 10,000 requests/minute, 2M tokens/minute

---

### 2. AWS Credentials

**Purpose**: Access AWS Cost Explorer and billing data

**How to Obtain**:

#### Option A: IAM User Access Keys (Recommended for Development)

1. **Sign in to AWS Console**: https://console.aws.amazon.com
2. **Navigate to IAM**: Services → IAM → Users
3. **Create User**:
   - Click "Add users"
   - Username: `cloudwise-finops-bot`
   - Select "Programmatic access"
4. **Set Permissions**:
   - Click "Attach policies directly"
   - Search and attach: `ViewOnlyAccess` (basic reading)
   - Create custom policy for Cost Explorer (see IAM policy above)
5. **Create Access Key**:
   - Click user → "Security credentials" tab
   - Click "Create access key"
   - Choose "Application running outside AWS"
   - Copy Access Key ID and Secret Access Key
6. **Configure AWS CLI**:
   ```bash
   aws configure
   # Enter Access Key ID
   # Enter Secret Access Key
   # Region: us-east-1 (or your preference)
   # Output format: json
   ```

#### Option B: IAM Role (Recommended for Production)

1. **Create IAM Role**: Services → IAM → Roles → Create role
2. **Select trusted entity**: AWS account → This account
3. **Attach permissions**: Same as Option A
4. **Configure in application**: Use AWS STS to assume role

**Required IAM Policy (Minimum)**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ce:*",
        "cur:DescribeReportDefinitions",
        "aws-portal:ViewBilling",
        "budgets:ViewBudget",
        "savingsplans:Describe*",
        "ec2:DescribeReservedInstances*",
        "ec2:DescribeSpotPriceHistory",
        "organizations:DescribeOrganization",
        "organizations:ListAccounts"
      ],
      "Resource": "*"
    }
  ]
}
```

**Cost**: AWS Cost Explorer API costs $0.01 per request. Budget $10-50/month depending on query frequency.

**Enable Cost Explorer**:
1. Visit https://console.aws.amazon.com/cost-management/home
2. Click "Enable Cost Explorer" (if not already enabled)
3. Wait 24 hours for initial data processing

---

### 3. Google Cloud Service Account

**Purpose**: Access GCP BigQuery billing export data

**How to Obtain**:

1. **Go to Google Cloud Console**: https://console.cloud.google.com
2. **Select or Create Project**: For billing analysis (e.g., "finops-project")
3. **Enable Required APIs**:
   - Navigate to "APIs & Services" → "Library"
   - Enable: "BigQuery API"
   - Enable: "Cloud Billing API"
   - Enable: "BigQuery Data Transfer Service API"
4. **Create Service Account**:
   - Navigate to "IAM & Admin" → "Service Accounts"
   - Click "Create Service Account"
   - Name: `cloudwise-finops-bot`
   - Description: "Service account for CloudWise FinOps agency"
5. **Grant Roles**:
   - `BigQuery User` (for running queries)
   - `BigQuery Data Viewer` (for reading billing data)
   - `Billing Account Viewer` (for billing API access)
6. **Create Key**:
   - Click on created service account
   - "Keys" tab → "Add Key" → "Create new key"
   - Select JSON format
   - Download and save securely (e.g., `gcp-service-account.json`)
7. **Set Environment Variable**:
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="/path/to/gcp-service-account.json"
   ```

**Enable Billing Export to BigQuery**:
1. **Navigate to Billing**: Console → Billing → Select billing account
2. **Billing Export**:
   - Click "Billing export" in left menu
   - Click "BigQuery export" tab
3. **Configure Standard Export**:
   - Click "Edit settings"
   - Select project containing your BigQuery dataset
   - Create or select dataset (e.g., "billing_export")
   - Click "Save"
4. **Configure Detailed Export** (Optional but Recommended):
   - Also enable "Detailed usage cost" export
   - Provides more granular cost data
5. **Wait for Data**: Takes 24-48 hours for first data to appear

**Cost**:
- BigQuery storage: First 10 GB free, then $0.02/GB/month
- BigQuery queries: First 1 TB/month free, then $5/TB
- Typical FinOps usage: $5-20/month

---

### 4. Azure Service Principal

**Purpose**: Access Azure Cost Management API

**How to Obtain**:

1. **Install Azure CLI**: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli
2. **Login to Azure**:
   ```bash
   az login
   ```
3. **Set Active Subscription**:
   ```bash
   az account set --subscription "Your Subscription Name or ID"
   ```
4. **Create Service Principal**:
   ```bash
   az ad sp create-for-rbac \
     --name "cloudwise-finops-bot" \
     --role "Cost Management Reader" \
     --scopes /subscriptions/<subscription-id>
   ```

   **Output** (save all values):
   ```json
   {
     "appId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
     "displayName": "cloudwise-finops-bot",
     "password": "xxxxxxxxxxxxxxxxxxxxxxxxxx",
     "tenant": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
   }
   ```

5. **Collect Required Values**:
   - `AZURE_TENANT_ID` = tenant
   - `AZURE_CLIENT_ID` = appId
   - `AZURE_CLIENT_SECRET` = password
   - `AZURE_SUBSCRIPTION_ID` = your subscription ID (get via `az account show`)

6. **Verify Permissions**:
   ```bash
   az role assignment list --assignee <appId> --subscription <subscription-id>
   ```

**Additional Roles (if needed)**:
- For reading resource details: `Reader` role at subscription scope
- For reservation data: `Reservation Reader` role

**Alternative: Portal Method**:
1. Azure Portal → Azure Active Directory → App registrations
2. New registration → Create
3. Certificates & secrets → New client secret → Save value
4. Go to Subscription → Access control (IAM) → Add role assignment
5. Select "Cost Management Reader" → Assign to service principal

**Cost**: Azure Cost Management API is free (no per-request charges)

---

### 5. Optional: Slack Webhook (for Alerts)

**Purpose**: Send anomaly alerts to Slack channel

**How to Obtain**:
1. Go to https://api.slack.com/apps
2. Click "Create New App" → "From scratch"
3. Name: "CloudWise FinOps Alerts"
4. Select workspace
5. Navigate to "Incoming Webhooks"
6. Toggle "Activate Incoming Webhooks" to On
7. Click "Add New Webhook to Workspace"
8. Select channel for alerts (e.g., #finops-alerts)
9. Copy webhook URL (starts with `https://hooks.slack.com/services/...`)

**Environment Variable**: `SLACK_WEBHOOK_URL`

**MCP Server Available**: `@modelcontextprotocol/server-slack` (for full Slack integration)

---

## Configuration Summary

### Environment Variables File (.env)

Create this file in your agency root directory:

```bash
# OpenAI (Required)
OPENAI_API_KEY=sk-...

# AWS (Required for AWS cost data)
AWS_PROFILE=default
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...

# GCP (Required for GCP cost data)
GOOGLE_APPLICATION_CREDENTIALS=/path/to/gcp-service-account.json
BIGQUERY_PROJECT=your-project-id

# Azure (Required for Azure cost data)
AZURE_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxx
AZURE_SUBSCRIPTION_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# Optional: Notifications
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...

# Optional: Database (if using PostgreSQL for caching)
DATABASE_URL=postgresql://user:pass@localhost:5432/finops
```

---

## Rate Limits & Quotas Consolidated

| Service | Rate Limit | Notes |
|---------|------------|-------|
| **AWS Cost Explorer** | No AWS limit | $0.01 per request |
| **AWS EC2** | ~100 req/sec | Implement exponential backoff |
| **GCP BigQuery** | 100 concurrent queries | First 1 TB queries/month free |
| **GCP Billing API** | 300 req/min (project)<br>975 req/min (org) | Can request increase |
| **Azure Cost Management** | 4 req/min/scope | Use ClientType header |
| **Azure Consumption API** | 10 req/min (subscription) | 6 req/min (other scopes) |
| **OpenAI GPT-4** | Tier-based (500-10,000 req/min) | Increases with spend |

---

## Cost Estimation for CloudWise Agency

### Monthly API Costs (Estimated)

**Scenario: Medium Enterprise (500 VMs across 3 clouds, hourly monitoring)**

| Service | Usage | Cost |
|---------|-------|------|
| AWS Cost Explorer | ~720 requests/month | $7.20 |
| GCP BigQuery | 100 GB storage, 500 GB queries | $7.00 |
| Azure Cost Management | Free | $0.00 |
| OpenAI API (GPT-4) | ~10,000 queries | $200-400 |
| **Total** | | **~$215-415/month** |

**Optimization Tips**:
- Cache cost data locally (SQLite MCP server) to reduce API calls
- Use AWS Cost Explorer sparingly; cache daily snapshots
- Leverage BigQuery's free tier by optimizing SQL queries
- Use GPT-4-mini for routine queries, GPT-4 for complex analysis

---

## Recommended MCP Server Configuration

**For cloudwise_finops agency, configure in each agent's `agent.py`:**

```python
from agency_swarm import Agent

cloud_connector = Agent(
    name="CloudConnector",
    description="Fetches and normalizes cost data from AWS, GCP, and Azure",
    instructions="./instructions.md",
    tools_folder="./tools",
    mcp_servers={
        "aws-cost-explorer": {
            "command": "uvx",
            "args": ["awslabs.cost-explorer-mcp-server@latest"],
            "env": {
                "AWS_PROFILE": "default",
                "AWS_REGION": "us-east-1"
            }
        },
        "bigquery": {
            "command": "./toolbox",
            "args": ["--prebuilt", "bigquery", "--stdio"],
            "env": {
                "BIGQUERY_PROJECT": "your-project-id"
            }
        },
        "azure-billing": {
            "command": "python",
            "args": ["-m", "mcp_azure_billing"],
            "env": {
                "AZURE_TENANT_ID": "your-tenant-id",
                "AZURE_CLIENT_ID": "your-client-id",
                "AZURE_CLIENT_SECRET": "your-client-secret",
                "AZURE_SUBSCRIPTION_ID": "your-subscription-id"
            }
        },
        "sqlite": {
            "command": "npx",
            "args": ["@modelcontextprotocol/server-sqlite", "./cost_cache.db"]
        }
    }
)
```

---

## Next Steps

1. **Collect API Keys**: Follow sections above to obtain all required credentials
2. **Test Each MCP Server**: Run individually to verify configuration
3. **Set Up Billing Exports**:
   - AWS: Enable Cost Explorer (wait 24h for data)
   - GCP: Configure BigQuery billing export (wait 24-48h)
   - Azure: Verify Cost Management access
4. **Review PRD**: Ensure tool allocation matches available MCP tools
5. **Implement Custom Tools**: For anomaly detection algorithms and optimization logic

---

## References

### AWS
- [AWS Cost Explorer API Documentation](https://docs.aws.amazon.com/cost-management/latest/userguide/ce-api.html)
- [AWS Cost Explorer MCP Server](https://awslabs.github.io/mcp/servers/cost-explorer-mcp-server)
- [AWS Billing and Cost Management MCP Server Announcement](https://aws.amazon.com/blogs/aws-cloud-financial-management/aws-announces-billing-and-cost-management-mcp-server/)

### GCP
- [Set up Cloud Billing data export to BigQuery](https://cloud.google.com/billing/docs/how-to/export-data-bigquery-setup)
- [Connect LLMs to BigQuery with MCP](https://docs.cloud.google.com/bigquery/docs/pre-built-tools-with-mcp-toolbox)
- [Use the BigQuery remote MCP server](https://docs.cloud.google.com/bigquery/docs/use-bigquery-mcp)

### Azure
- [Azure Billing MCP Server (PyPI)](https://pypi.org/project/mcp-azure-billing/)
- [Microsoft Cost Management REST APIs](https://learn.microsoft.com/en-us/rest/api/cost-management/)
- [Azure MCP Server Documentation](https://learn.microsoft.com/en-us/azure/developer/azure-mcp-server/get-started)

### MCP Protocol
- [Model Context Protocol Servers](https://github.com/modelcontextprotocol/servers)
- [Official MCP Registry](https://registry.modelcontextprotocol.io/)
- [FinOps.org MCP Use Case](https://www.finops.org/wg/model-context-protocol-mcp-ai-for-finops-use-case/)

### Community MCP Servers
- [AWS FinOps MCP Server](https://github.com/ravikiranvm/aws-finops-mcp-server)
- [GCP MCP Server](https://github.com/eniayomi/gcp-mcp)
- [Azure Pricing MCP Server](https://github.com/charris-msft/azure-pricing-mcp)
- [BigQuery MCP Server](https://github.com/LucasHild/mcp-server-bigquery)

---

## Appendix: Custom Tool Requirements

The following tools **cannot** be implemented via MCP and require custom BaseTool implementations:

### Anomaly Detector Agent (3 custom tools)
1. **CalculateBaseline**: Statistical analysis (moving averages, seasonal decomposition)
2. **DetectSpike**: Threshold-based anomaly detection (Z-score, percentage deviation)
3. **ClassifyAnomaly**: Rule-based classification (cost spike, usage spike, new resource)

### Optimizer Agent (2 custom tools)
1. **AnalyzeRightsizing**: Compare actual usage vs. instance size (requires compute optimization logic)
2. **CalculateArbitrage**: Cross-cloud price comparison and workload portability analysis

### Policy Engine Agent (1 custom tool)
1. **ValidateAction**: Business logic for approval workflows and policy compliance

**Implementation Note**: These tools will process data fetched by MCP servers but apply domain-specific FinOps algorithms.
