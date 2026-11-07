#ifndef EVIDENCE_LOGGER_H
#define EVIDENCE_LOGGER_H

#include <Arduino.h>
#include <mbedtls/sha256.h>
#include "module_interface.h"
#include "diagnostic_logger.h"
#include "system_config.h"
#include "events.h"

/**
 * @file evidence_logger.h
 * @brief SHA-256 Tamper-Evident Cryptographic Forensic Evidence Logger.
 *
 * ForensiTap-ESP32 Appliance
 *
 * Implements an immutable, append-only cryptographic hash chain where each
 * block contains a cryptographic digest of its contents coupled with the
 * hash of the preceding block (prev_hash).
 */

#define MAX_EVIDENCE_BLOCKS 32
#define GENESIS_PREV_HASH "0000000000000000000000000000000000000000000000000000000000000000"

/**
 * @brief Forensic block record in the cryptographic evidence chain.
 */
struct EvidenceBlock {
    uint32_t index;              ///< Monotonically increasing sequence index (0 = Genesis)
    uint32_t timestampMs;        ///< System uptime in milliseconds when block was sealed
    char     eventType[24];      ///< Canonical event type string (e.g., "SYSTEM_BOOT", "TRAFFIC_SPIKE")
    char     severity[12];       ///< Severity rating ("INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL")
    char     description[88];    ///< Human-readable or structured payload summary
    char     prevHash[65];       ///< 64-char hex SHA-256 digest of preceding block
    char     blockHash[65];      ///< 64-char hex SHA-256 digest of this block
};

/**
 * @brief Verification result structure.
 */
struct ChainVerificationResult {
    bool     isValid;
    uint32_t checkedBlocks;
    uint32_t failedIndex;
    char     failureReason[64];
};

class ForensiTapEvidenceLogger : public IModule {
public:
    ForensiTapEvidenceLogger();
    virtual ~ForensiTapEvidenceLogger() {}

    // IModule Lifecycle Interface
    virtual const char* getName() const override { return "EVID"; }
    virtual bool init(const SystemConfig& config) override;
    virtual void update(unsigned long currentMillis) override;
    virtual bool isHealthy() const override;
    virtual void printDiagnostics() override;

    // Cryptographic Evidence Ingestion
    void logEvidence(const char* eventType, const char* severity, const char* description);

    // Cryptographic Chain Verification
    ChainVerificationResult verifyChainIntegrity() const;

    // Retrieval Accessors
    uint32_t getTotalBlocksCreated() const { return m_totalBlocksCreated; }
    uint16_t getStoredBlockCount() const { return m_storedBlockCount; }
    uint16_t getMaxBlockCapacity() const { return MAX_EVIDENCE_BLOCKS; }
    const EvidenceBlock* getStoredBlocks() const { return m_blocks; }
    const char* getGenesisHash() const { return m_genesisHash; }
    const char* getTipHash() const { return m_tipHash; }

    // Static Utility: SHA-256 calculation to lowercase hex
    static bool computeSha256Hex(const char* input, size_t inputLen, char* outHex65);

    // Static Utility: Formats canonical input string for hashing
    static void buildCanonicalString(char* dest, size_t maxLen,
                                     uint32_t index, uint32_t timestampMs,
                                     const char* eventType, const char* severity,
                                     const char* description, const char* prevHash);

private:
    void mintGenesisBlock();

    EvidenceBlock m_blocks[MAX_EVIDENCE_BLOCKS];
    uint16_t      m_storedBlockCount;
    uint32_t      m_totalBlocksCreated;
    char          m_genesisHash[65];
    char          m_tipHash[65];
    bool          m_isInitialized;
};

extern ForensiTapEvidenceLogger g_evidenceLogger;

#endif // EVIDENCE_LOGGER_H
