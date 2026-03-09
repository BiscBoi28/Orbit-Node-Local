# ORBIT CyberGraph Visualization Layer

Comprehensive visualization toolkit for the ORBIT cybersecurity graph database, providing both monitoring dashboards and interactive exploration capabilities.

## 🎯 Components

### NeoDash Dashboards (`dashboards/`)

Real-time monitoring dashboards for:

- Security posture overview
- Vulnerability tracking and analysis
- Asset classification and crown jewel monitoring
- ActionCard workflow management
- Threat intelligence visualization

### Neo4j Bloom Configuration (`bloom/`)

Interactive graph exploration with:

- Preconfigured perspectives for security analysis
- Search phrases for common investigation patterns
- Visual styling for node/relationship differentiation
- Guided exploration workflows

### Analytics Queries (`queries/`)

Reusable Cypher queries for:

- Security metrics and KPIs
- Relationship analysis and path finding
- Data quality and integrity checks
- Performance monitoring queries

## 🚀 Quick Start

1. **Prerequisites**

   ```bash
   # Ensure Neo4j is running with populated data
   docker compose up -d

   # Verify data exists
   python ../neo4j-local/execution/tests/test_schema.py
   ```

2. **Install NeoDash**
   - Option A: Use hosted version at https://neodash.graphapp.io
   - Option B: Install as Neo4j Desktop plugin
   - Connect to: `bolt://localhost:7687`

3. **Load Dashboard**

   ```bash
   # Import the main dashboard configuration
   # File: dashboards/orbit-security-dashboard.json
   ```

4. **Configure Bloom**
   ```bash
   # Import perspective configuration
   # File: bloom/orbit-security-perspective.json
   ```

## 📊 Dashboard Overview

### Security Operations Dashboard

- **System Health**: Host count, service inventory, data asset classification
- **Vulnerability Management**: CVE tracking, severity distribution, patch status
- **Threat Intelligence**: Active threats, exploitation chains, risk assessment
- **Workflow Monitoring**: ActionCard pipeline, analyst workload, SLA tracking

### Asset Intelligence Dashboard

- **Crown Jewel Analysis**: High-sensitivity asset identification and protection status
- **Data Classification**: PII distribution, sensitivity scoring, compliance gaps
- **Risk Assessment**: Asset-threat correlation, vulnerability exposure analysis

## 🔍 Bloom Exploration Patterns

### Predefined Search Phrases

- `"Show crown jewel assets"` - Displays high-value data assets
- `"Find vulnerable hosts"` - Shows hosts with active CVEs
- `"Trace threat paths"` - Maps attack chains through vulnerabilities
- `"Show pending actions"` - Displays ActionCards awaiting analyst review
- `"Asset impact analysis"` - Shows relationships for specific assets

### Visual Styling

- **Hosts**: Blue nodes with hostname labels
- **Threats**: Red nodes with severity-based sizing
- **Crown Jewels**: Gold nodes with enhanced borders
- **Vulnerabilities**: Orange nodes with CVSS scoring
- **ActionCards**: Green/yellow/red based on status

## 🛠️ Customization

### Adding New Dashboard Widgets

1. Create Cypher query in `queries/custom/`
2. Test query in Neo4j Browser
3. Add widget to dashboard JSON
4. Configure visualization type (chart, table, graph)

### Extending Bloom Perspectives

1. Edit perspective JSON configuration
2. Add new search phrases for common patterns
3. Update visual styling rules
4. Test with sample data

## 📁 File Structure

```
visualization/
├── README.md                           # This file
├── setup/
│   ├── install-neodash.md             # NeoDash installation guide
│   ├── configure-bloom.md             # Bloom setup instructions
│   └── sample-data-generator.py       # Test data for visualization
├── dashboards/
│   ├── orbit-security-dashboard.json  # Main security operations dashboard
│   ├── asset-intelligence.json        # Asset-focused dashboard
│   └── threat-analysis.json           # Threat intelligence dashboard
├── bloom/
│   ├── orbit-security-perspective.json # Main Bloom perspective
│   ├── search-phrases.cypher          # Predefined search patterns
│   └── styling-rules.json             # Visual styling configuration
└── queries/
    ├── dashboard/                     # Dashboard widget queries
    │   ├── security-overview.cypher
    │   ├── vulnerability-metrics.cypher
    │   ├── asset-classification.cypher
    │   └── workflow-monitoring.cypher
    ├── analytics/                     # Advanced analysis queries
    │   ├── risk-assessment.cypher
    │   ├── relationship-analysis.cypher
    │   └── compliance-reports.cypher
    └── maintenance/                   # Database health queries
        ├── data-quality-checks.cypher
        └── performance-monitoring.cypher
```

## 🎨 Visualization Best Practices

### Dashboard Design

- Use consistent color schemes aligned with security severity levels
- Implement drill-down capabilities for detailed investigation
- Include time-based filters for temporal analysis
- Provide exportable reports and metrics

### Bloom Configuration

- Create role-based perspectives for different analyst types
- Use semantic search phrases matching analyst vocabulary
- Implement progressive disclosure for complex relationships
- Include contextual help and guided workflows

## 🧪 Testing

### Dashboard Testing

```bash
# Generate test data
python setup/sample-data-generator.py

# Verify dashboard queries
python -m pytest tests/test_dashboard_queries.py
```

### Bloom Testing

```bash
# Validate search phrases
python tests/test_search_phrases.py

# Check perspective configuration
python tests/test_bloom_config.py
```

## 📈 Monitoring & Maintenance

### Performance Monitoring

- Monitor query execution times for dashboard widgets
- Track memory usage during large graph explorations
- Optimize slow queries with appropriate indexes

### Data Quality

- Validate visualization data matches source database
- Check for missing relationships or orphaned nodes
- Monitor dashboard refresh rates and data staleness

---

**Next Steps**: Follow the setup guides in `setup/` to configure your visualization environment.
