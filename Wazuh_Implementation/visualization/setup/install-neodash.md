# NeoDash Installation & Setup Guide

NeoDash is a low-code dashboard builder for Neo4j that enables creating interactive dashboards using Cypher queries.

## 📦 Installation Options

### Option 1: Hosted Version (Recommended)

1. Navigate to https://neodash.graphapp.io
2. No installation required - runs in browser
3. Connect to your local Neo4j instance

### Option 2: Neo4j Desktop Plugin

1. Open Neo4j Desktop
2. Go to **Graph Apps** tab
3. Search for "NeoDash"
4. Click **Install**
5. Launch from your database project

### Option 3: Docker Deployment

```bash
# Run NeoDash in Docker container
docker run -it --rm -p 5005:5005 nielsdejong/neodash:2.4
```

### Option 4: Local Development Setup

```bash
# Clone NeoDash repository
git clone https://github.com/neo4j-labs/neodash.git
cd neodash

# Install dependencies
npm install

# Start development server
npm start
```

## 🔌 Database Connection

### Connection Parameters

- **Protocol**: `bolt://`
- **Host**: `localhost`
- **Port**: `7687`
- **Database**: `neo4j` (default)
- **Username**: `neo4j`
- **Password**: `orbit_secure_pass` (or your configured password)

### Connection String Examples

```
bolt://localhost:7687
bolt://neo4j:orbit_secure_pass@localhost:7687
neo4j://localhost:7687  # For Neo4j 4.0+
```

## 📊 Dashboard Import Process

### 1. Import Main Security Dashboard

```bash
# File location: ../dashboards/orbit-security-dashboard.json
```

**Steps:**

1. Open NeoDash interface
2. Click **Load Dashboard**
3. Select `orbit-security-dashboard.json`
4. Verify connection settings
5. Click **Load**

### 2. Configure Dashboard Settings

```json
{
  "title": "ORBIT Security Operations Center",
  "theme": "dark",
  "refresh_rate": "30s",
  "connection": {
    "protocol": "bolt",
    "hostname": "localhost",
    "port": 7687,
    "database": "neo4j"
  }
}
```

### 3. Test Dashboard Functionality

- Verify all widgets load data correctly
- Test interactive filters and drill-downs
- Check real-time data refresh
- Validate export functionality

## 🎨 Customization Options

### Theme Configuration

```javascript
// Available themes
themes = [
  "light", // Default light theme
  "dark", // Dark mode for SOCs
  "blue", // Corporate blue theme
  "red", // High-contrast red theme
];
```

### Widget Types Available

- **Bar Charts**: Vulnerability counts, threat severity
- **Pie Charts**: Asset distribution, status breakdown
- **Line Graphs**: Temporal trend analysis
- **Tables**: Detailed data listings with sorting
- **Graphs**: Network visualizations with layouts
- **Single Values**: KPIs and summary statistics
- **Maps**: Geospatial data visualization

### Custom Styling

```css
/* Custom CSS for ORBIT branding */
.neodash-dashboard {
  --primary-color: #1f4e79;
  --secondary-color: #f39c12;
  --warning-color: #e74c3c;
  --success-color: #2ecc71;
}
```

## 🔧 Performance Optimization

### Query Optimization

```cypher
// Use LIMIT for large datasets
MATCH (h:Host)
RETURN count(h) AS total_hosts
LIMIT 1000

// Add indexes for filtered properties
CREATE INDEX idx_actioncard_priority
FOR (ac:ActionCard) ON (ac.priority)

// Use parameters for dynamic filters
MATCH (v:Vulnerability)
WHERE v.severity = $severity_filter
RETURN v.cve_id, v.cvss
```

### Caching Configuration

```json
{
  "cache_settings": {
    "enable_caching": true,
    "cache_duration": "5m",
    "auto_refresh": true,
    "refresh_interval": "30s"
  }
}
```

## 🚨 Troubleshooting

### Common Connection Issues

1. **"Connection refused"**
   - Check Neo4j service is running: `docker ps`
   - Verify port 7687 is accessible
   - Check firewall settings

2. **"Authentication failed"**
   - Verify username/password combination
   - Check if authentication is enabled in Neo4j

3. **"Database not found"**
   - Confirm database name spelling
   - Check if database exists: `SHOW DATABASES`

### Performance Issues

1. **Slow dashboard loading**
   - Add database indexes for filtered properties
   - Reduce result set sizes with LIMIT clauses
   - Use query profiling: `PROFILE MATCH...`

2. **Memory issues**
   - Increase Neo4j heap size in docker-compose.yml
   - Optimize queries to avoid Cartesian products
   - Use streaming for large datasets

## 🔐 Security Considerations

### Access Control

```javascript
// Role-based dashboard access
const dashboardPermissions = {
  analyst: ["security-overview", "vulnerability-tracking"],
  admin: ["*"], // All dashboards
  viewer: ["security-overview"], // Read-only
};
```

### Data Privacy

- Ensure sensitive data is pseudonymized in visualizations
- Implement query result filtering based on user roles
- Audit dashboard access and query execution

## 📈 Monitoring & Maintenance

### Health Checks

```cypher
// Verify dashboard data freshness
MATCH (n)
WHERE n.last_updated > datetime() - duration('PT1H')
RETURN labels(n) AS entity_type, count(n) AS recent_updates
```

### Performance Monitoring

```cypher
// Monitor query execution times
PROFILE MATCH (h:Host)-[:HAS_VULNERABILITY]->(v:Vulnerability)
RETURN h.hostname, count(v) AS vulnerability_count
ORDER BY vulnerability_count DESC
LIMIT 10
```

---

**Next Steps**:

1. Import the ORBIT security dashboard from `../dashboards/`
2. Configure connection to your Neo4j instance
3. Test all dashboard widgets and functionality
4. Customize styling and themes as needed
