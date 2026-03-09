-- ================================================
-- ORBIT Machine Learning and Statistical Analysis Queries
-- ================================================
-- Data preparation, feature engineering, and statistical analysis for ML/AI cybersecurity models

-- === FEATURE ENGINEERING FOR ML MODELS ===

-- Host Risk Feature Vector Generation
MATCH (h:Host)
OPTIONAL MATCH (h)<-[:RESIDES_ON]-(d:DataAsset)
OPTIONAL MATCH (h)-[:HAS_VULNERABILITY]->(v:Vulnerability)
OPTIONAL MATCH (v)<-[:EXPLOITS]-(t:Threat)
OPTIONAL MATCH (h)-[:CONNECTS_TO]-(connected:Host)
WITH h,
     count(DISTINCT d) AS asset_count,
     count(DISTINCT [asset IN collect(d) WHERE asset.crown_jewel = true]) AS crown_jewel_count,
     COALESCE(avg([asset IN collect(d) | asset.sensitivity_score]), 0) AS avg_asset_sensitivity,
     count(DISTINCT v) AS vulnerability_count,
     COALESCE(avg(v.cvss), 0) AS avg_cvss_score,
     COALESCE(max(v.cvss), 0) AS max_cvss_score,
     count(DISTINCT t) AS threat_count,
     COALESCE(avg(t.confidence), 0) AS avg_threat_confidence,
     count(DISTINCT connected) AS network_connectivity
WITH h,
     asset_count,
     crown_jewel_count,
     round(avg_asset_sensitivity * 100) / 100 AS avg_asset_sensitivity,
     vulnerability_count,
     round(avg_cvss_score * 10) / 10 AS avg_cvss_score,
     round(max_cvss_score * 10) / 10 AS max_cvss_score,
     threat_count,
     round(avg_threat_confidence * 100) / 100 AS avg_threat_confidence,
     network_connectivity,
     // Calculate composite risk score as target variable
     (crown_jewel_count * 0.4) + 
     (avg_asset_sensitivity * 0.2) + 
     (vulnerability_count * 0.01) + 
     (avg_cvss_score * 0.1) + 
     (threat_count * 0.05) + 
     (avg_threat_confidence * 0.1) + 
     (network_connectivity * 0.02) AS composite_risk_score
RETURN h.hostname AS host_id,
       // Categorical features
       coalesce(h.os_name + ' ' + h.os_version, h.os_name, 'Unknown') AS operating_system,
       CASE 
           WHEN crown_jewel_count > 0 THEN 'high_value'
           WHEN avg_asset_sensitivity >= 0.7 THEN 'sensitive'
           WHEN asset_count >= 5 THEN 'asset_rich'
           ELSE 'standard'
       END AS host_classification,
       // Numerical features
       asset_count,
       crown_jewel_count,
       avg_asset_sensitivity,
       vulnerability_count,
       avg_cvss_score,
       max_cvss_score,
       threat_count,
       avg_threat_confidence,
       network_connectivity,
       // Target variable
       round(composite_risk_score * 100) / 100 AS risk_score_target,
       // Risk category for classification models
       CASE
           WHEN composite_risk_score >= 1.0 THEN 'critical'
           WHEN composite_risk_score >= 0.6 THEN 'high'
           WHEN composite_risk_score >= 0.3 THEN 'medium'
           ELSE 'low'
       END AS risk_category_target
ORDER BY composite_risk_score DESC;

-- Asset Sensitivity Prediction Features
MATCH (d:DataAsset)
WHERE d.sensitivity_score IS NOT NULL
MATCH (d)-[:RESIDES_ON]->(h:Host)
WITH d, h,
     size(d.pii_types) AS pii_type_count,
     CASE WHEN 'US_SSN' IN d.pii_types THEN 1 ELSE 0 END AS has_ssn,
     CASE WHEN 'CREDIT_CARD' IN d.pii_types THEN 1 ELSE 0 END AS has_credit_card,
     CASE WHEN 'EMAIL_ADDRESS' IN d.pii_types THEN 1 ELSE 0 END AS has_email,
     CASE WHEN 'PHONE_NUMBER' IN d.pii_types THEN 1 ELSE 0 END AS has_phone,
     CASE WHEN 'US_DRIVER_LICENSE' IN d.pii_types THEN 1 ELSE 0 END AS has_license,
     CASE WHEN d.scan_ts IS NOT NULL 
          THEN duration.between(datetime(d.scan_ts), datetime()).days 
          ELSE null END AS days_since_scan
OPTIONAL MATCH (h)-[:HAS_VULNERABILITY]->(v:Vulnerability)
WITH d, h, pii_type_count, has_ssn, has_credit_card, has_email, has_phone, has_license, days_since_scan,
     count(v) AS host_vulnerability_count,
     COALESCE(max(v.cvss), 0) AS host_max_cvss
RETURN d.location_pseudonym AS asset_id,
       // Features for sensitivity prediction
       pii_type_count,
       has_ssn,
       has_credit_card, 
       has_email,
       has_phone,
       has_license,
       COALESCE(days_since_scan, 999) AS days_since_scan,
       h.os AS host_os,
       host_vulnerability_count,
       host_max_cvss,
       // Target variable
       round(d.sensitivity_score * 100) / 100 AS sensitivity_score_actual,
       // Binned target for classification
       CASE
           WHEN d.sensitivity_score >= 0.8 THEN 'very_high'
           WHEN d.sensitivity_score >= 0.6 THEN 'high' 
           WHEN d.sensitivity_score >= 0.4 THEN 'medium'
           WHEN d.sensitivity_score >= 0.2 THEN 'low'
           ELSE 'minimal'
       END AS sensitivity_category_actual
ORDER BY d.sensitivity_score DESC;

-- === TIME SERIES DATA FOR TEMPORAL MODELS ===

-- ActionCard Creation Time Series (Weekly Aggregation)
MATCH (ac:ActionCard)
WHERE ac.created_ts IS NOT NULL 
  AND datetime(ac.created_ts) > datetime() - duration('P52W')
WITH date.truncate('week', date(datetime(ac.created_ts))) AS week_start,
     collect(ac) AS weekly_actioncards
RETURN week_start AS time_period,
       count(weekly_actioncards) AS total_actioncards,
       size([ac IN weekly_actioncards WHERE ac.priority = 'critical']) AS critical_count,
       size([ac IN weekly_actioncards WHERE ac.priority = 'high']) AS high_count,
       size([ac IN weekly_actioncards WHERE ac.priority = 'medium']) AS medium_count,
       size([ac IN weekly_actioncards WHERE ac.priority = 'low']) AS low_count,
       size([ac IN weekly_actioncards WHERE ac.status = 'completed']) AS completed_count,
       size([ac IN weekly_actioncards WHERE ac.status = 'pending']) AS pending_count,
       // Calculate weekly trend indicators
       round(size([ac IN weekly_actioncards WHERE ac.priority = 'critical']) * 100.0 / count(weekly_actioncards)) AS critical_percentage,
       round(size([ac IN weekly_actioncards WHERE ac.status = 'completed']) * 100.0 / count(weekly_actioncards)) AS completion_rate
ORDER BY week_start;

-- Threat Discovery Time Series with Confidence Metrics
MATCH (t:Threat)
WHERE t.first_seen IS NOT NULL 
  AND datetime(t.first_seen) > datetime() - duration('P26W')
WITH date.truncate('week', date(datetime(t.first_seen))) AS week_start,
     collect(t) AS weekly_threats
RETURN week_start AS time_period,
       count(weekly_threats) AS threat_count,
       round(avg([threat IN weekly_threats | threat.confidence]) * 100) / 100 AS avg_confidence,
       round(stdev([threat IN weekly_threats | threat.confidence]) * 100) / 100 AS confidence_std_dev,
       size([threat IN weekly_threats WHERE threat.priority = 'critical']) AS critical_threats,
       size([threat IN weekly_threats WHERE threat.verification_status = 'verified']) AS verified_threats,
       // Trend indicators
       size(reduce(unique_actors = [], threat IN weekly_threats | 
           CASE WHEN threat.actor IS NOT NULL AND NOT threat.actor IN unique_actors 
                THEN unique_actors + threat.actor ELSE unique_actors END)) AS unique_threat_actors,
       size(reduce(unique_categories = [], threat IN weekly_threats | 
           CASE WHEN NOT threat.category IN unique_categories 
                THEN unique_categories + threat.category ELSE unique_categories END)) AS threat_category_diversity
ORDER BY week_start;

-- === ANOMALY DETECTION DATASETS ===

-- Daily Security Events Baseline for Anomaly Detection
WITH range(0, 90) AS day_range
UNWIND day_range AS days_back
WITH date() - duration({days: days_back}) AS analysis_date
OPTIONAL MATCH (ac:ActionCard)
WHERE date.truncate('day', date(datetime(ac.created_ts))) = analysis_date
OPTIONAL MATCH (d:DataAsset)
WHERE date.truncate('day', date(datetime(d.scan_ts))) = analysis_date
OPTIONAL MATCH (t:Threat)
WHERE date.truncate('day', date(datetime(t.first_seen))) = analysis_date
WITH analysis_date,
     count(ac) AS actioncard_events,
     count(d) AS asset_scan_events,
     count(t) AS threat_discovery_events
RETURN analysis_date,
       actioncard_events,
       asset_scan_events,
       threat_discovery_events,
       actioncard_events + asset_scan_events + threat_discovery_events AS total_security_events,
       // Features for anomaly detection
       CASE WHEN dayOfWeek(analysis_date) IN [1, 7] THEN 1 ELSE 0 END AS is_weekend,
       dayOfWeek(analysis_date) AS day_of_week,
       analysis_date.week AS week_of_year,
       analysis_date.month AS month_of_year
ORDER BY analysis_date DESC;

-- Host Behavior Patterns for Outlier Detection
MATCH (h:Host)
OPTIONAL MATCH (h)<-[:RESIDES_ON]-(d:DataAsset)
WHERE d.scan_ts IS NOT NULL
OPTIONAL MATCH (h)-[:HAS_VULNERABILITY]->(v:Vulnerability)
OPTIONAL MATCH (h)<-[:RESIDES_ON]-(asset:DataAsset)<-[:AFFECTS]-(ac:ActionCard)
WHERE ac.created_ts IS NOT NULL 
  AND datetime(ac.created_ts) > datetime() - duration('P30D')
WITH h,
     count(DISTINCT d) AS assets_scanned_recently,
     count(DISTINCT v) AS current_vulnerabilities,
     count(DISTINCT ac) AS recent_actioncards,
     avg([scan_asset IN collect(d) | 
          duration.between(datetime(scan_asset.scan_ts), datetime()).days]) AS avg_scan_age,
     max([scan_asset IN collect(d) | 
          duration.between(datetime(scan_asset.scan_ts), datetime()).days]) AS oldest_scan_age
RETURN h.hostname AS host_id,
       coalesce(h.os_name + ' ' + h.os_version, h.os_name, 'Unknown') AS operating_system,
       assets_scanned_recently,
       current_vulnerabilities,
       recent_actioncards,
       round(COALESCE(avg_scan_age, 0)) AS avg_scan_age_days,
       COALESCE(oldest_scan_age, 0) AS oldest_scan_age_days,
       // Composite behavior score for outlier detection
       (assets_scanned_recently * 0.2) + 
       (current_vulnerabilities * 0.3) + 
       (recent_actioncards * 0.4) + 
       (CASE WHEN avg_scan_age > 60 THEN -0.5 ELSE 0.1 END) AS behavior_activity_score
ORDER BY behavior_activity_score;

-- === CLUSTERING AND SEGMENTATION ===

-- Asset Clustering Features for Unsupervised Learning
MATCH (d:DataAsset)-[:RESIDES_ON]->(h:Host)
WITH d, h,
     size(d.pii_types) AS pii_diversity,
     CASE WHEN d.crown_jewel THEN 1 ELSE 0 END AS is_crown_jewel_binary,
     CASE WHEN d.scan_ts IS NOT NULL 
          THEN duration.between(datetime(d.scan_ts), datetime()).days 
          ELSE 999 END AS scan_recency
OPTIONAL MATCH (h)-[:HAS_VULNERABILITY]->(v:Vulnerability)
OPTIONAL MATCH (h)-[:CONNECTS_TO]-(connected:Host)
WITH d, h, pii_diversity, is_crown_jewel_binary, scan_recency,
     count(v) AS host_vulnerabilities,
     count(connected) AS network_connections,
     COALESCE(avg(v.cvss), 0) AS avg_host_cvss
RETURN d.location_pseudonym AS asset_id,
       // Clustering features (all normalized)
       round(d.sensitivity_score * 100) / 100 AS sensitivity_normalized,
       pii_diversity AS pii_type_count,
       is_crown_jewel_binary,
       CASE 
           WHEN scan_recency <= 7 THEN 4
           WHEN scan_recency <= 30 THEN 3
           WHEN scan_recency <= 90 THEN 2
           WHEN scan_recency <= 180 THEN 1
           ELSE 0
       END AS scan_recency_score,
       LEAST(host_vulnerabilities, 10) AS vulnerability_count_capped,
       LEAST(network_connections, 20) AS connectivity_capped,
       round(avg_host_cvss * 10) / 10 AS host_risk_score,
       // Additional categorical features for mixed-type clustering
       h.os AS host_operating_system,
       CASE 
           WHEN d.sensitivity_score >= 0.8 THEN 'tier_1'
           WHEN d.sensitivity_score >= 0.5 THEN 'tier_2'
           ELSE 'tier_3'
       END AS sensitivity_tier
ORDER BY d.sensitivity_score DESC;

-- === PREDICTIVE MODEL TRAINING SETS ===

-- Vulnerability Exploitation Prediction Dataset
MATCH (v:Vulnerability)
OPTIONAL MATCH (v)<-[:EXPLOITS]-(t:Threat)
OPTIONAL MATCH (v)<-[:HAS_VULNERABILITY]-(h:Host)<-[:RESIDES_ON]-(d:DataAsset)
WITH v, 
     count(t) AS exploitation_count,
     count(DISTINCT h) AS affected_hosts,
     count(DISTINCT d) AS affected_assets,
     COALESCE(max(t.confidence), 0) AS max_threat_confidence,
     size([asset IN collect(d) WHERE asset.crown_jewel = true]) AS crown_jewel_exposure
RETURN v.cve_id AS vulnerability_id,
       // Features
       v.cvss AS cvss_score,
       v.type AS vulnerability_type,
       affected_hosts,
       affected_assets,
       crown_jewel_exposure,
       round(max_threat_confidence * 100) / 100 AS max_threat_confidence,
       CASE WHEN v.published IS NOT NULL 
            THEN duration.between(date(datetime(v.published)), date()).days 
            ELSE null END AS days_since_publication,
       // Target variable: Is this vulnerability being actively exploited?
       CASE WHEN exploitation_count > 0 THEN 1 ELSE 0 END AS is_exploited_binary,
       exploitation_count AS exploitation_intensity,
       // Risk category target
       CASE 
           WHEN exploitation_count >= 3 THEN 'high_exploitation'
           WHEN exploitation_count >= 1 THEN 'active_exploitation'  
           ELSE 'no_exploitation'
       END AS exploitation_category
ORDER BY exploitation_count DESC, v.cvss DESC;

-- === STATISTICAL ANALYSIS QUERIES ===

-- Correlation Analysis: Sensitivity Score vs PII Types
MATCH (d:DataAsset)
WHERE d.sensitivity_score IS NOT NULL AND size(d.pii_types) > 0
WITH size(d.pii_types) AS pii_count, d.sensitivity_score AS sensitivity
WITH collect(pii_count) AS pii_counts, collect(sensitivity) AS sensitivities,
     avg(pii_count) AS avg_pii, avg(sensitivity) AS avg_sensitivity,
     count(*) AS n
UNWIND range(0, n-1) AS i
WITH pii_counts[i] AS pii, sensitivities[i] AS sens, avg_pii, avg_sensitivity, n
WITH sum((pii - avg_pii) * (sens - avg_sensitivity)) AS numerator,
     sqrt(sum((pii - avg_pii)^2)) AS pii_variance,
     sqrt(sum((sens - avg_sensitivity)^2)) AS sens_variance,
     n, avg_pii, avg_sensitivity
RETURN round(avg_pii * 100) / 100 AS average_pii_types,
       round(avg_sensitivity * 100) / 100 AS average_sensitivity_score,
       round((numerator / (pii_variance * sens_variance)) * 100) / 100 AS correlation_coefficient,
       n AS sample_size,
       CASE 
           WHEN abs(numerator / (pii_variance * sens_variance)) >= 0.7 THEN 'Strong Correlation'
           WHEN abs(numerator / (pii_variance * sens_variance)) >= 0.4 THEN 'Moderate Correlation'
           WHEN abs(numerator / (pii_variance * sens_variance)) >= 0.2 THEN 'Weak Correlation'
           ELSE 'No Significant Correlation'
       END AS correlation_interpretation;

-- Distribution Analysis for Model Validation
MATCH (d:DataAsset)
WHERE d.sensitivity_score IS NOT NULL
WITH d.sensitivity_score AS score
WITH collect(score) AS scores, count(score) AS n
WITH scores, n, 
     reduce(sum = 0.0, score IN scores | sum + score) / n AS mean,
     apoc.coll.min(scores) AS minimum,
     apoc.coll.max(scores) AS maximum
WITH scores, n, mean, minimum, maximum,
     sqrt(reduce(variance = 0.0, score IN scores | variance + (score - mean)^2) / (n - 1)) AS std_dev,
     apoc.coll.sort(scores) AS sorted_scores
WITH n, mean, minimum, maximum, std_dev, sorted_scores,
     sorted_scores[toInteger(n * 0.25)] AS q1,
     sorted_scores[toInteger(n * 0.5)] AS median,
     sorted_scores[toInteger(n * 0.75)] AS q3
RETURN n AS sample_size,
       round(mean * 1000) / 1000 AS mean_sensitivity,
       round(std_dev * 1000) / 1000 AS standard_deviation,
       round(minimum * 1000) / 1000 AS minimum_value,
       round(q1 * 1000) / 1000 AS first_quartile,
       round(median * 1000) / 1000 AS median_value,
       round(q3 * 1000) / 1000 AS third_quartile,
       round(maximum * 1000) / 1000 AS maximum_value,
       round((q3 - q1) * 1000) / 1000 AS interquartile_range,
       // Skewness calculation (simplified)
       CASE 
           WHEN mean > median THEN 'Right Skewed (Positive)'
           WHEN mean < median THEN 'Left Skewed (Negative)'
           ELSE 'Approximately Normal'
       END AS distribution_skew;