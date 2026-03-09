# Neo4j Bloom Configuration Guide

Neo4j Bloom is a graph exploration and visualization tool that enables business users to interact with Neo4j databases through a natural, visual interface.

## 📦 Installation & Access

### Neo4j Desktop (Recommended)

1. Open Neo4j Desktop
2. Select your ORBIT database project
3. Click **Open** → **Neo4j Bloom**
4. Bloom launches automatically with database connection

### Neo4j Browser Plugin

1. Navigate to Neo4j Browser (`http://localhost:7474`)
2. Go to **Applications** tab
3. Install **Neo4j Bloom** plugin
4. Launch from browser interface

### Standalone Installation

```bash
# Download Bloom from Neo4j website
# Requires valid Neo4j license for production use
```

## 🎯 Perspective Configuration

### ORBIT Security Perspective

**File**: `../bloom/orbit-security-perspective.json`

```json
{
  "name": "ORBIT Security Analysis",
  "description": "Cybersecurity graph exploration for threat analysis and asset management",
  "nodes": {
    "Host": {
      "display_property": "hostname",
      "size_property": "vulnerability_count",
      "color": "#3498db"
    },
    "DataAsset": {
      "display_property": "location_pseudonym",
      "size_property": "sensitivity_score",
      "color": "{crown_jewel ? '#f1c40f' : '#95a5a6'}"
    },
    "Vulnerability": {
      "display_property": "cve_id",
      "size_property": "cvss",
      "color": "#e67e22"
    },
    "Threat": {
      "display_property": "title",
      "size_property": "severity",
      "color": "#e74c3c"
    },
    "ActionCard": {
      "display_property": "summary",
      "color": "{status === 'pending' ? '#f39c12' : status === 'completed' ? '#2ecc71' : '#e74c3c'}"
    }
  },
  "relationships": {
    "HAS_VULNERABILITY": { "color": "#e67e22", "thickness": 2 },
    "EXPLOITED_BY": { "color": "#e74c3c", "thickness": 3 },
    "AFFECTS": { "color": "#9b59b6", "thickness": 2 },
    "RESIDES_ON": { "color": "#3498db", "thickness": 1 }
  }
}
```

### Import Perspective

1. Open Bloom interface
2. Click **Perspectives** → **Import**
3. Select `orbit-security-perspective.json`
4. Set as default perspective for ORBIT analysis

## 🔍 Search Phrases Configuration

### Security Analysis Phrases

**File**: `../bloom/search-phrases.cypher`

```cypher
-- Show all crown jewel assets with their hosting details
"Show crown jewel assets"
MATCH (d:DataAsset {crown_jewel: true})-[:RESIDES_ON]->(h:Host)
RETURN d, h

-- Find hosts with high vulnerability counts
"Find vulnerable hosts"
MATCH (h:Host)-[r:HAS_VULNERABILITY]->(v:Vulnerability)
WITH h, count(v) AS vuln_count
WHERE vuln_count >= 5
RETURN h

-- Trace threat exploitation paths
"Trace threat paths"
MATCH path = (h:Host)-[:HAS_VULNERABILITY]->(v:Vulnerability)-[:EXPLOITED_BY]->(t:Threat)
RETURN path

-- Show pending ActionCards requiring analyst attention
"Show pending actions"
MATCH (ac:ActionCard {status: 'pending'})-[:AFFECTS]->(target)
RETURN ac, target

-- Asset impact analysis for specific host
"Asset impact for {hostname}"
MATCH (h:Host {hostname: $hostname})<-[:RESIDES_ON]-(d:DataAsset)
OPTIONAL MATCH (h)-[:HAS_VULNERABILITY]->(v:Vulnerability)
OPTIONAL MATCH (d)<-[:AFFECTS]-(ac:ActionCard)
RETURN h, d, v, ac

-- Find assets containing specific PII types
"Show assets with {pii_type}"
MATCH (d:DataAsset)
WHERE $pii_type IN d.pii_types
RETURN d

-- Threat severity analysis
"Show {severity} threats"
MATCH (t:Threat {severity: $severity})<-[:EXPLOITED_BY]-(v:Vulnerability)<-[:HAS_VULNERABILITY]-(h:Host)
RETURN t, v, h

-- ActionCard workflow analysis
"Show {status} ActionCards"
MATCH (ac:ActionCard {status: $status})
OPTIONAL MATCH (ac)-[:ASSIGNED_TO]->(an:Analyst)
OPTIONAL MATCH (ac)-[:AFFECTS]->(target)
RETURN ac, an, target

-- Host service inventory
"Show services on {hostname}"
MATCH (h:Host {hostname: $hostname})-[:RUNS]->(s:Service)
OPTIONAL MATCH (h)-[:HAS_APP]->(app:Application)
RETURN h, s, app

-- Data sensitivity distribution
"Show high sensitivity assets"
MATCH (d:DataAsset)
WHERE d.sensitivity_score >= 0.6
MATCH (d)-[:RESIDES_ON]->(h:Host)
RETURN d, h
ORDER BY d.sensitivity_score DESC
```

### Natural Language Patterns

```cypher
-- Pattern: "What threatens [asset_name]?"
MATCH (d:DataAsset {location_pseudonym: $asset_name})-[:RESIDES_ON]->(h:Host)
MATCH (h)-[:HAS_VULNERABILITY]->(v:Vulnerability)-[:EXPLOITED_BY]->(t:Threat)
RETURN d, h, v, t

-- Pattern: "Show me the attack surface for [hostname]"
MATCH (h:Host {hostname: $hostname})
MATCH (h)-[:RUNS]->(s:Service)
MATCH (h)-[:HAS_VULNERABILITY]->(v:Vulnerability)
MATCH (h)<-[:RESIDES_ON]-(d:DataAsset)
RETURN h, s, v, d

-- Pattern: "Which analysts are working on [threat_type]?"
MATCH (t:Threat)-[:EXPLOITED_BY]->(v:Vulnerability)<-[:HAS_VULNERABILITY]-(h:Host)
MATCH (h)<-[:AFFECTS]-(ac:ActionCard)-[:ASSIGNED_TO]->(an:Analyst)
WHERE toLower(t.title) CONTAINS toLower($threat_type)
RETURN DISTINCT an, ac, t, h
```

## 🎨 Visual Styling Rules

### Node Styling Configuration

```json
{
  "node_styles": {
    "Host": {
      "base_color": "#3498db",
      "border_width": 2,
      "size_range": [20, 60],
      "icon": "server",
      "label_position": "bottom"
    },
    "DataAsset": {
      "base_color": "#95a5a6",
      "crown_jewel_color": "#f1c40f",
      "crown_jewel_border": "#e67e22",
      "border_width": "{crown_jewel ? 4 : 2}",
      "size_range": [15, 50],
      "icon": "database"
    },
    "Vulnerability": {
      "color_by_cvss": {
        "0-3.9": "#2ecc71", // Low
        "4.0-6.9": "#f39c12", // Medium
        "7.0-8.9": "#e67e22", // High
        "9.0-10": "#e74c3c" // Critical
      },
      "size_range": [10, 40],
      "icon": "warning"
    },
    "Threat": {
      "color_by_severity": {
        "LOW": "#f39c12",
        "MEDIUM": "#e67e22",
        "HIGH": "#e74c3c",
        "CRITICAL": "#8e44ad"
      },
      "pulse_animation": true,
      "size_range": [15, 45]
    },
    "ActionCard": {
      "color_by_status": {
        "received": "#3498db",
        "pending": "#f39c12",
        "approved": "#2ecc71",
        "executing": "#9b59b6",
        "completed": "#27ae60",
        "rejected": "#95a5a6",
        "failed": "#e74c3c"
      },
      "border_style": "dashed",
      "icon": "clipboard"
    }
  },
  "relationship_styles": {
    "HAS_VULNERABILITY": {
      "color": "#e67e22",
      "thickness": 2,
      "style": "solid"
    },
    "EXPLOITED_BY": {
      "color": "#e74c3c",
      "thickness": 3,
      "style": "solid",
      "animation": "flow"
    },
    "AFFECTS": {
      "color": "#9b59b6",
      "thickness": 2,
      "style": "dashed"
    },
    "RESIDES_ON": {
      "color": "#3498db",
      "thickness": 1,
      "style": "solid"
    }
  }
}
```

### Scene Layouts

```json
{
  "layouts": {
    "security_overview": {
      "type": "hierarchical",
      "direction": "top-down",
      "node_spacing": 100,
      "level_separation": 150
    },
    "threat_analysis": {
      "type": "force_directed",
      "iterations": 500,
      "spring_length": 80,
      "spring_constant": 0.0001
    },
    "asset_relationships": {
      "type": "circular",
      "radius": 200,
      "center_node_type": "DataAsset"
    }
  }
}
```

## 🚀 Advanced Configuration

### Role-Based Perspectives

```json
{
  "perspectives": {
    "security_analyst": {
      "visible_nodes": ["Host", "Vulnerability", "Threat", "ActionCard"],
      "visible_relationships": ["HAS_VULNERABILITY", "EXPLOITED_BY", "AFFECTS"],
      "default_queries": ["Show pending actions", "Find vulnerable hosts"]
    },
    "compliance_officer": {
      "visible_nodes": ["DataAsset", "Host", "ActionCard"],
      "visible_relationships": ["RESIDES_ON", "AFFECTS"],
      "default_queries": [
        "Show crown jewel assets",
        "Show high sensitivity assets"
      ]
    },
    "infrastructure_admin": {
      "visible_nodes": ["Host", "Service", "Application"],
      "visible_relationships": ["RUNS", "HAS_APP"],
      "default_queries": [
        "Show services on {hostname}",
        "Asset impact for {hostname}"
      ]
    }
  }
}
```

### Custom Bloom Rules

```javascript
// Dynamic node sizing based on properties
bloom.setNodeSizeRule("DataAsset", function (node) {
  return Math.max(20, Math.min(60, node.sensitivity_score * 60));
});

// Conditional node coloring
bloom.setNodeColorRule("ActionCard", function (node) {
  const statusColors = {
    pending: "#f39c12",
    approved: "#2ecc71",
    rejected: "#e74c3c",
    completed: "#27ae60",
  };
  return statusColors[node.status] || "#95a5a6";
});

// Relationship visibility rules
bloom.setRelationshipVisibilityRule(function (rel, sourceNode, targetNode) {
  // Hide low-priority relationships in complex views
  if (rel.type === "AFFECTS" && sourceNode.confidence < 0.7) {
    return false;
  }
  return true;
});
```

## 🧪 Testing & Validation

### Perspective Validation

```cypher
// Test search phrase functionality
CALL bloom.perspective.search("Show crown jewel assets")
YIELD nodes, relationships
RETURN count(nodes) AS node_count, count(relationships) AS rel_count

// Validate styling rules application
MATCH (d:DataAsset {crown_jewel: true})
RETURN d.asset_hash, d.sensitivity_score
LIMIT 5

// Check performance of complex queries
PROFILE MATCH path = (h:Host)-[:HAS_VULNERABILITY]->(v:Vulnerability)-[:EXPLOITED_BY]->(t:Threat)
RETURN count(path) AS threat_paths
```

### User Experience Testing

1. Test all predefined search phrases
2. Validate visual styling for different node types
3. Check performance with realistic data volumes
4. Verify role-based perspective functionality

---

**Next Steps**:

1. Import the ORBIT security perspective
2. Configure search phrases for your analyst workflows
3. Test visual styling with sample data
4. Create role-specific perspectives as needed
