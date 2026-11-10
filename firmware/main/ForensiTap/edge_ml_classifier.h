#ifndef EDGE_ML_CLASSIFIER_H
#define EDGE_ML_CLASSIFIER_H

#include <Arduino.h>
#include "feature_engine.h"

/**
 * @file edge_ml_classifier.h
 * @brief High-efficiency embedded decision tree classifier running on ESP32 Core 1.
 *
 * ForensiTap-ESP32 Appliance (Sub-millisecond Edge Inference)
 */

struct EdgeMLInference {
    bool        isAnomaly;
    float       anomalyScore;       ///< 0.0 to 1.0 confidence score
    const char* attackCategory;     ///< "DEAUTH_FLOOD", "MGMT_STORM", "RECON_SCAN", "BURST_SPIKE", "BENIGN"
    const char* rootCauseSummary;   ///< Explanatory attribution string
};

class EdgeMLClassifier {
public:
    static EdgeMLInference classify(const FeatureVector& feat) {
        EdgeMLInference result;
        result.isAnomaly = false;
        result.anomalyScore = 0.05f;
        result.attackCategory = "BENIGN";
        result.rootCauseSummary = "Normal ambient 802.11 wireless activity within baseline bounds.";

        // If baseline isn't ready, evaluate only gross physical anomalies
        if (!feat.baselineReady && feat.deauthRate < 5.0f && feat.frameRate < 150.0f) {
            return result;
        }

        // Branch 1: High-confidence Deauth / Disassociation Flooding
        if (feat.deauthRate >= 3.0f || (feat.frameRate > 10.0f && feat.deauthRatio >= 0.15f)) {
            result.isAnomaly = true;
            result.anomalyScore = 0.96f;
            result.attackCategory = "DEAUTH_FLOOD";
            result.rootCauseSummary = "Targeted 802.11 deauth storm detected. Attacker forcing client re-association.";
            return result;
        }

        // Branch 2: High Z-Score Spike with High Burstiness (DoS / Scanning)
        if (feat.rateDeviationZScore >= 3.0f && feat.burstScore >= 3.5f) {
            result.isAnomaly = true;
            result.anomalyScore = 0.92f;
            result.attackCategory = "BURST_SPIKE";
            result.rootCauseSummary = "High-velocity traffic surge exceeding +3.0σ standard deviations with acute burstiness.";
            return result;
        }

        // Branch 3: Excessive Management Overhead Storm
        if (feat.frameRate > 15.0f && feat.managementRatio >= 0.65f) {
            result.isAnomaly = true;
            result.anomalyScore = 0.88f;
            result.attackCategory = "MGMT_STORM";
            result.rootCauseSummary = "Severe management frame ratio saturation. Probable beacon flood or probe storm.";
            return result;
        }

        // Branch 4: Rapid Peer Table Expansion (Reconnaissance / Wardriving)
        if (feat.uniquePeers >= 28 && feat.burstScore >= 3.0f) {
            result.isAnomaly = true;
            result.anomalyScore = 0.82f;
            result.attackCategory = "RECON_SCAN";
            result.rootCauseSummary = "Airspace table near capacity with bursty MAC appearances. Potential active RF wardriving.";
            return result;
        }

        // Moderate Statistical Departure
        if (feat.rateDeviationZScore >= 2.5f) {
            result.isAnomaly = true;
            result.anomalyScore = 0.70f;
            result.attackCategory = "TRAFFIC_SPIKE";
            result.rootCauseSummary = "Moderate traffic elevation deviating from EWMA profile.";
            return result;
        }

        return result;
    }
};

#endif // EDGE_ML_CLASSIFIER_H
